#!/usr/bin/env python3
"""Finish Apple notarization on a cheap Linux runner.

The macOS build submits the signed DMG and exits. Pending work is a pair of
assets on the draft GitHub release ``notarize-queue``:

  pending-<submission-id>.json
  pending-<submission-id>.dmg

This script lists those assets and returns immediately when the list is empty.
Otherwise it asks Apple's Notary API (one GET, no polling loop) what happened:

  GET https://appstoreconnect.apple.com/notary/v2/submissions/{id}

In Progress stays queued. Accepted is stapled with ``rcodesign staple``,
checked with ``rcodesign print-signature-info``, and the stapled DMG replaces the release
asset. Invalid or Rejected prints the notary log, drops the pending marker,
and fails the process.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

QUEUE_TAG = os.environ.get("NOTARIZE_QUEUE_TAG", "notarize-queue")
NOTARY_API = "https://appstoreconnect.apple.com/notary/v2/submissions"
RCODESIGN_VERSION = "0.29.0"
RCODESIGN_SHA256 = "dbe85cedd8ee4217b64e9a0e4c2aef92ab8bcaaa41f20bde99781ff02e600002"
RCODESIGN_URL = (
    "https://github.com/indygreg/apple-platform-rs/releases/download/"
    f"apple-codesign/{RCODESIGN_VERSION}/"
    f"apple-codesign-{RCODESIGN_VERSION}-x86_64-unknown-linux-musl.tar.gz"
)


def classify_status(status: str) -> str:
    """Map an Apple notary status onto accepted, rejected, or pending."""
    normalized = status.strip().lower()
    if normalized == "accepted":
        return "accepted"
    if normalized in {"invalid", "rejected"}:
        return "rejected"
    return "pending"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def b64url(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _der_len(data: bytes, index: int) -> tuple[int, int]:
    first = data[index]
    index += 1
    if first < 0x80:
        return first, index
    count = first & 0x7F
    if count == 0 or index + count > len(data):
        raise ValueError("truncated DER length")
    length = int.from_bytes(data[index : index + count], "big")
    return length, index + count


def _p256_int(raw: bytes) -> bytes:
    stripped = raw.lstrip(b"\x00") or b"\x00"
    if len(stripped) > 32:
        raise ValueError("ECDSA integer does not fit P-256")
    return stripped.rjust(32, b"\x00")


def der_ecdsa_to_raw(der: bytes) -> bytes:
    """Convert an OpenSSL DER ECDSA signature to the raw R||S form JWT uses."""
    if not der or der[0] != 0x30:
        raise ValueError("expected DER SEQUENCE")
    seq_len, index = _der_len(der, 1)
    end = index + seq_len
    if end > len(der):
        raise ValueError("truncated DER signature")
    if der[index] != 0x02:
        raise ValueError("expected DER INTEGER r")
    r_len, index = _der_len(der, index + 1)
    r = der[index : index + r_len]
    index += r_len
    if index >= end or der[index] != 0x02:
        raise ValueError("expected DER INTEGER s")
    s_len, index = _der_len(der, index + 1)
    s = der[index : index + s_len]
    return _p256_int(r) + _p256_int(s)


def apple_jwt(key_pem: str, key_id: str, issuer: str) -> str:
    header = b64url(
        json.dumps({"alg": "ES256", "kid": key_id, "typ": "JWT"}, separators=(",", ":")).encode("ascii")
    )
    now = int(time.time())
    payload = b64url(
        json.dumps(
            {"iss": issuer, "iat": now, "exp": now + 600, "aud": "appstoreconnect-v1"},
            separators=(",", ":"),
        ).encode("ascii")
    )
    signing_input = f"{header}.{payload}".encode("ascii")
    pem = key_pem if key_pem.endswith("\n") else key_pem + "\n"
    fd, key_path = tempfile.mkstemp(prefix="asc-key-", suffix=".p8")
    try:
        os.write(fd, pem.encode("utf-8"))
        os.close(fd)
        os.chmod(key_path, stat.S_IRUSR | stat.S_IWUSR)
        proc = subprocess.run(
            ["openssl", "dgst", "-sha256", "-sign", key_path],
            input=signing_input,
            capture_output=True,
            check=False,
        )
        if proc.returncode != 0:
            detail = proc.stderr.decode("utf-8", "replace").strip()
            raise RuntimeError(f"openssl could not sign the App Store Connect JWT: {detail}")
        signature = b64url(der_ecdsa_to_raw(proc.stdout))
    finally:
        os.remove(key_path)
    return f"{header}.{payload}.{signature}"


def run_gh(args: list[str], check: bool = True) -> subprocess.CompletedProcess[str]:
    command = ["gh", *args]
    print("+", " ".join(command), flush=True)
    proc = subprocess.run(command, capture_output=True, text=True, check=False)
    if proc.stdout:
        sys.stdout.write(proc.stdout if proc.stdout.endswith("\n") else proc.stdout + "\n")
    if check and proc.returncode != 0:
        detail = proc.stderr.strip() or f"exit {proc.returncode}"
        raise RuntimeError(detail)
    return proc


def queue_assets(repo: str) -> list[dict[str, object]] | None:
    """Return assets, or None when the draft queue release does not exist yet."""
    proc = run_gh(
        ["release", "view", QUEUE_TAG, "--repo", repo, "--json", "assets"],
        check=False,
    )
    if proc.returncode != 0:
        detail = (proc.stderr or "") + (proc.stdout or "")
        if "not found" in detail.lower():
            return None
        raise RuntimeError(detail.strip() or f"gh release view exited {proc.returncode}")
    payload = json.loads(proc.stdout or "{}")
    assets = payload.get("assets") or []
    if not isinstance(assets, list):
        raise RuntimeError("gh release view returned assets that are not a list")
    return assets


def pending_json_assets(assets: list[dict[str, object]]) -> list[dict[str, object]]:
    pending = []
    for asset in assets:
        name = str(asset.get("name") or "")
        if name.startswith("pending-") and name.endswith(".json"):
            pending.append(asset)
    return pending


def download_asset(repo: str, name: str, dest_dir: Path) -> Path:
    dest_dir.mkdir(parents=True, exist_ok=True)
    run_gh(
        [
            "release",
            "download",
            QUEUE_TAG,
            "--repo",
            repo,
            "--pattern",
            name,
            "--dir",
            str(dest_dir),
            "--clobber",
        ]
    )
    path = dest_dir / name
    if not path.is_file():
        raise RuntimeError(f"download of {name} did not produce a file")
    return path


def delete_asset(repo: str, asset_id: object) -> None:
    run_gh(["api", "-X", "DELETE", f"repos/{repo}/releases/assets/{asset_id}"])


def asset_id_by_name(assets: list[dict[str, object]], name: str) -> object | None:
    for asset in assets:
        if asset.get("name") == name:
            return asset.get("id")
    return None


def http_json(url: str, token: str | None) -> dict[str, object]:
    headers = {"Accept": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            body = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")
        raise RuntimeError(f"GET {url} failed: HTTP {exc.code} {detail}") from exc
    payload = json.loads(body or "{}")
    if not isinstance(payload, dict):
        raise RuntimeError(f"GET {url} did not return a JSON object")
    return payload


def notary_status(token: str, submission_id: str) -> str:
    payload = http_json(f"{NOTARY_API}/{submission_id}", token)
    data = payload.get("data")
    if not isinstance(data, dict):
        raise RuntimeError(f"notary status response has no data object: {payload}")
    attributes = data.get("attributes")
    if not isinstance(attributes, dict):
        raise RuntimeError(f"notary status response has no attributes: {payload}")
    status = attributes.get("status")
    if not isinstance(status, str) or not status:
        raise RuntimeError(f"notary status response has no status: {payload}")
    return status


def fetch_notary_log(token: str, submission_id: str) -> str:
    payload = http_json(f"{NOTARY_API}/{submission_id}/logs", token)
    data = payload.get("data")
    attributes = data.get("attributes") if isinstance(data, dict) else None
    log_url = attributes.get("developerLogUrl") if isinstance(attributes, dict) else None
    if not isinstance(log_url, str) or not log_url:
        return json.dumps(payload, indent=2)
    request = urllib.request.Request(log_url)
    with urllib.request.urlopen(request, timeout=120) as response:
        return response.read().decode("utf-8", "replace")


def ensure_rcodesign(cache_dir: Path) -> Path:
    binary = cache_dir / "rcodesign"
    if binary.is_file() and os.access(binary, os.X_OK):
        return binary
    cache_dir.mkdir(parents=True, exist_ok=True)
    archive = cache_dir / "apple-codesign.tar.gz"
    print(f"Downloading rcodesign {RCODESIGN_VERSION}", flush=True)
    urllib.request.urlretrieve(RCODESIGN_URL, archive)
    digest = sha256_file(archive)
    if digest != RCODESIGN_SHA256:
        raise RuntimeError(f"rcodesign tarball sha256 {digest} != {RCODESIGN_SHA256}")
    subprocess.run(["tar", "-xzf", str(archive), "-C", str(cache_dir)], check=True)
    found = list(cache_dir.rglob("rcodesign"))
    if not found:
        raise RuntimeError("rcodesign binary missing from the apple-codesign tarball")
    shutil.copy2(found[0], binary)
    binary.chmod(binary.stat().st_mode | stat.S_IXUSR)
    return binary


def run_rcodesign(binary: Path, args: list[str]) -> None:
    command = [str(binary), *args]
    print("+", " ".join(command), flush=True)
    proc = subprocess.run(command, check=False)
    if proc.returncode != 0:
        raise RuntimeError(f"rcodesign {' '.join(args)} exited {proc.returncode}")


def release_exists(repo: str, tag: str) -> bool:
    proc = run_gh(["release", "view", tag, "--repo", repo, "--json", "tagName"], check=False)
    if proc.returncode == 0:
        return True
    detail = ((proc.stderr or "") + (proc.stdout or "")).lower()
    if "not found" in detail:
        return False
    raise RuntimeError((proc.stderr or proc.stdout or "").strip() or f"gh release view {tag} failed")


def upload_stapled(repo: str, tag: str, dmg_path: Path) -> None:
    run_gh(["release", "upload", tag, "--repo", repo, str(dmg_path), "--clobber"])


def write_record(output: Path, submission_id: str, dmg: Path, dmg_name: str) -> None:
    run_id = os.environ.get("GITHUB_RUN_ID", "")
    repository = os.environ.get("GITHUB_REPOSITORY", "")
    server = os.environ.get("GITHUB_SERVER_URL", "https://github.com").rstrip("/")
    run_url = ""
    if repository and run_id:
        run_url = f"{server}/{repository}/actions/runs/{run_id}"
    record = {
        "submission_id": submission_id,
        "run_id": run_id,
        "run_attempt": os.environ.get("GITHUB_RUN_ATTEMPT", ""),
        "repository": repository,
        "dmg_name": dmg_name,
        "sha256": sha256_file(dmg),
        "target_tag": os.environ.get("RELEASE_TAG", ""),
        "workflow": os.environ.get("GITHUB_WORKFLOW", ""),
        "workflow_run_url": run_url,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")


def load_records(repo: str, work: Path) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    assets = queue_assets(repo)
    if not assets:
        return [], []
    records = []
    for asset in pending_json_assets(assets):
        name = str(asset["name"])
        path = download_asset(repo, name, work / "markers")
        record = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(record, dict) or not record.get("submission_id"):
            raise RuntimeError(f"{name} is not a notarization record")
        record["_asset_id"] = asset.get("id")
        record["_asset_name"] = name
        records.append(record)
    return records, assets


def wanted(record: dict[str, object], submission_id: str, run_id: str) -> bool:
    if submission_id and str(record.get("submission_id") or "") != submission_id:
        return False
    if run_id and str(record.get("run_id") or "") != run_id:
        return False
    return True


def mark_done(repo: str, assets: list[dict[str, object]], record: dict[str, object]) -> None:
    names = [str(record.get("_asset_name") or "")]
    submission_id = str(record.get("submission_id") or "")
    names.append(f"pending-{submission_id}.dmg")
    for name in names:
        if not name:
            continue
        asset_id = asset_id_by_name(assets, name)
        if asset_id is None:
            continue
        print(f"Removing queue asset {name}", flush=True)
        delete_asset(repo, asset_id)


def process_record(
    repo: str,
    record: dict[str, object],
    assets: list[dict[str, object]],
    token: str,
    rcodesign_cache: Path,
    output_dir: Path,
) -> str:
    submission_id = str(record["submission_id"])
    status = notary_status(token, submission_id)
    print(f"submission {submission_id} status={status}", flush=True)
    kind = classify_status(status)
    if kind == "pending":
        print(f"submission {submission_id} still {status}; leaving the queue marker", flush=True)
        return "pending"
    if kind == "rejected":
        log_text = fetch_notary_log(token, submission_id)
        print(f"Notary log for {submission_id} ({status}):\n{log_text}", flush=True)
        log_path = output_dir / f"failed-{submission_id}.log"
        output_dir.mkdir(parents=True, exist_ok=True)
        log_path.write_text(log_text, encoding="utf-8")
        try:
            run_gh(
                [
                    "release",
                    "upload",
                    QUEUE_TAG,
                    "--repo",
                    repo,
                    f"{log_path}#failed-{submission_id}.log",
                    "--clobber",
                ]
            )
        except RuntimeError as exc:
            print(f"WARNING: could not upload the notary log: {exc}", flush=True)
        mark_done(repo, assets, record)
        return "rejected"

    target_tag = str(record.get("target_tag") or "")
    if target_tag and not release_exists(repo, target_tag):
        print(
            f"submission {submission_id} is Accepted but release {target_tag} is not published yet",
            flush=True,
        )
        return "pending"

    dmg_asset = f"pending-{submission_id}.dmg"
    if asset_id_by_name(assets, dmg_asset) is None:
        raise RuntimeError(f"queue is missing {dmg_asset}")
    downloaded = download_asset(repo, dmg_asset, output_dir / "download" / submission_id)
    expected = str(record.get("sha256") or "")
    actual = sha256_file(downloaded)
    if expected and actual.lower() != expected.lower():
        raise RuntimeError(f"DMG sha256 {actual} does not match queued {expected}")
    print(f"Notary log for {submission_id}:\n{fetch_notary_log(token, submission_id)}", flush=True)
    rcodesign = ensure_rcodesign(rcodesign_cache)
    run_rcodesign(rcodesign, ["staple", "-v", str(downloaded)])
    # rcodesign verify only accepts Mach-O; print-signature-info reads DMGs.
    run_rcodesign(rcodesign, ["print-signature-info", "-v", str(downloaded)])
    stapled_sha = sha256_file(downloaded)
    print(f"stapled sha256 {stapled_sha}", flush=True)
    output_dir.mkdir(parents=True, exist_ok=True)
    published_name = str(record.get("dmg_name") or "openrv-macos-arm64.dmg")
    published = output_dir / published_name
    shutil.copy2(downloaded, published)
    if target_tag:
        upload_stapled(repo, target_tag, published)
        print(f"Replaced {published_name} on release {target_tag}", flush=True)
    else:
        print(f"No target release tag; stapled DMG is {published}", flush=True)
    mark_done(repo, assets, record)
    return "stapled"


def cmd_finish() -> int:
    repo = os.environ.get("GITHUB_REPOSITORY") or os.environ.get("GH_REPO") or ""
    if not repo:
        print("GITHUB_REPOSITORY is required", file=sys.stderr)
        return 1
    submission_filter = os.environ.get("NOTARIZE_SUBMISSION_ID", "").strip()
    run_filter = os.environ.get("NOTARIZE_RUN_ID", "").strip()
    output_dir = Path(os.environ.get("NOTARIZE_OUTPUT_DIR", "notarize-out"))
    with tempfile.TemporaryDirectory(prefix="notarize-markers-") as tmp:
        records, assets = load_records(repo, Path(tmp))
    selected = [record for record in records if wanted(record, submission_filter, run_filter)]
    if not selected:
        print("no pending notarization submissions", flush=True)
        return 0
    missing = [name for name in ("ASC_KEY_ID", "ASC_ISSUER_ID", "ASC_API_KEY_P8") if not os.environ.get(name)]
    if missing:
        print("Apple secrets missing while submissions are pending: " + ", ".join(missing), file=sys.stderr)
        return 1
    token = apple_jwt(os.environ["ASC_API_KEY_P8"], os.environ["ASC_KEY_ID"], os.environ["ASC_ISSUER_ID"])
    cache = Path(os.environ.get("RCODESIGN_CACHE", str(output_dir / ".rcodesign")))
    failures = 0
    # Refresh the asset list per item so a delete sees ids from the latest view.
    for record in selected:
        submission_id = str(record.get("submission_id"))
        try:
            fresh = queue_assets(repo) or []
            outcome = process_record(repo, record, fresh, token, cache, output_dir)
        except (RuntimeError, urllib.error.URLError, OSError, json.JSONDecodeError, ValueError) as exc:
            print(f"ERROR submission {submission_id}: {exc}", file=sys.stderr)
            failures += 1
            continue
        if outcome == "rejected":
            failures += 1
    return 1 if failures else 0


def cmd_write_record(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="notarize_finish.py write-record")
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--submission-id", required=True)
    parser.add_argument("--dmg", required=True, type=Path)
    parser.add_argument("--dmg-name", required=True)
    args = parser.parse_args(argv)
    if not args.dmg.is_file():
        print(f"DMG not found: {args.dmg}", file=sys.stderr)
        return 1
    write_record(args.output, args.submission_id, args.dmg, args.dmg_name)
    print(f"Wrote {args.output}", flush=True)
    return 0


def _self_check_queue(kind: str) -> None:
    """Run finish against a fake gh that either has no release or no assets."""
    with tempfile.TemporaryDirectory(prefix="notarize-self-") as tmp:
        root = Path(tmp)
        bin_dir = root / "bin"
        bin_dir.mkdir()
        fake = bin_dir / "gh"
        if kind == "missing":
            script = "#!/bin/sh\necho 'release not found' >&2\nexit 1\n"
        else:
            script = "#!/bin/sh\necho '{\"assets\":[]}'\nexit 0\n"
        fake.write_text(script, encoding="utf-8")
        fake.chmod(0o755)
        env = os.environ.copy()
        env["PATH"] = f"{bin_dir}{os.pathsep}{env.get('PATH', '')}"
        env["GITHUB_REPOSITORY"] = "example/OpenRV"
        env.pop("ASC_KEY_ID", None)
        env.pop("ASC_ISSUER_ID", None)
        env.pop("ASC_API_KEY_P8", None)
        env["NOTARIZE_SUBMISSION_ID"] = ""
        env["NOTARIZE_RUN_ID"] = ""
        proc = subprocess.run(
            [sys.executable, str(Path(__file__).resolve()), "finish"],
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        if proc.returncode != 0 or "no pending notarization submissions" not in proc.stdout:
            raise RuntimeError(f"self-check {kind} failed:\n{proc.stdout}\n{proc.stderr}")


def _self_check_der() -> None:
    if shutil.which("openssl") is None:
        print("openssl not on PATH; skipping DER self-check")
        return
    with tempfile.TemporaryDirectory(prefix="notarize-der-") as tmp:
        key = Path(tmp) / "key.pem"
        subprocess.run(
            ["openssl", "ecparam", "-name", "prime256v1", "-genkey", "-noout", "-out", str(key)],
            check=True,
            capture_output=True,
        )
        proc = subprocess.run(
            ["openssl", "dgst", "-sha256", "-sign", str(key)],
            input=b"notarize-finish",
            capture_output=True,
            check=True,
        )
        raw = der_ecdsa_to_raw(proc.stdout)
        if len(raw) != 64:
            raise RuntimeError(f"DER conversion produced {len(raw)} bytes")


def cmd_self_check() -> int:
    samples = {
        "Accepted": "accepted",
        "accepted": "accepted",
        "Invalid": "rejected",
        "Rejected": "rejected",
        "In Progress": "pending",
        "": "pending",
    }
    for status, expected in samples.items():
        got = classify_status(status)
        if got != expected:
            print(f"classify({status!r}) = {got}, expected {expected}", file=sys.stderr)
            return 1
    with tempfile.TemporaryDirectory(prefix="notarize-record-") as tmp:
        root = Path(tmp)
        dmg = root / "sample.dmg"
        dmg.write_bytes(b"not a real dmg")
        output = root / "notarize-pending.json"
        saved = {key: os.environ.get(key) for key in ("GITHUB_RUN_ID", "GITHUB_REPOSITORY", "RELEASE_TAG")}
        os.environ["GITHUB_RUN_ID"] = "4242"
        os.environ["GITHUB_REPOSITORY"] = "example/OpenRV"
        os.environ["RELEASE_TAG"] = "v9.9.9"
        try:
            write_record(output, "11111111-2222-3333-4444-555555555555", dmg, "sample.dmg")
        finally:
            for key, value in saved.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value
        record = json.loads(output.read_text(encoding="utf-8"))
        if record["sha256"] != hashlib.sha256(b"not a real dmg").hexdigest():
            print("write-record sha256 mismatch", file=sys.stderr)
            return 1
        if record["submission_id"] != "11111111-2222-3333-4444-555555555555":
            print("write-record dropped the submission id", file=sys.stderr)
            return 1
        if record["target_tag"] != "v9.9.9" or record["run_id"] != "4242":
            print(f"write-record fields unexpected: {record}", file=sys.stderr)
            return 1
    _self_check_queue("empty")
    _self_check_queue("missing")
    _self_check_der()
    print("notarize_finish self-check ok")
    return 0


def main(argv: list[str]) -> int:
    command = argv[0] if argv else "finish"
    if command == "finish":
        return cmd_finish()
    if command == "write-record":
        return cmd_write_record(argv[1:])
    if command == "self-check":
        return cmd_self_check()
    print(f"unknown command {command}", file=sys.stderr)
    print("usage: notarize_finish.py [finish|write-record|self-check]", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
