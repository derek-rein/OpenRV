"""Copy vendor playback runtimes and refuse everything else.

The private app directory may contain unmodified dynamic libraries and, on
macOS, a framework bundle. Headers, static libraries, samples, and docs are
never copied. Logs name only the rejected file, never a directory listing.
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

FORBIDDEN_SUFFIXES = {
    ".h",
    ".hpp",
    ".hh",
    ".hxx",
    ".inl",
    ".idl",
    ".a",
    ".lib",
    ".pdb",
    ".exp",
    ".obj",
    ".o",
    ".c",
    ".cc",
    ".cpp",
    ".cxx",
    ".mm",
    ".m",
    ".pdf",
    ".html",
    ".htm",
    ".md",
    ".txt",
    ".rtf",
}
FORBIDDEN_DIR_NAMES = {
    "include",
    "includes",
    "headers",
    "documents",
    "docs",
    "documentation",
    "samples",
    "sample",
    "examples",
}


def safe_print(*args: object, file=None) -> None:
    out = file if file is not None else sys.stdout
    try:
        print(*args, file=out)
    except UnicodeEncodeError:
        text = " ".join(str(arg) for arg in args)
        encoding = getattr(out, "encoding", None) or "utf-8"
        raw = text.encode(encoding, errors="replace").decode(encoding, errors="replace")
        print(raw, file=out)


def is_macos_junk_name(name: str) -> bool:
    return name == ".DS_Store" or name.startswith("._")


def is_dynamic_library(path: Path) -> bool:
    name = path.name.lower()
    if is_macos_junk_name(name):
        return False
    if name.endswith(".dylib") or name.endswith(".dll"):
        return True
    return ".so" in name


def _forbidden_file(path: Path) -> bool:
    name = path.name.lower()
    if is_macos_junk_name(name):
        return True
    if path.suffix.lower() in FORBIDDEN_SUFFIXES:
        return True
    return name in {"blackmagicrawapi.h", "r3dsdk.h"}


def _purge_forbidden(root: Path) -> None:
    for path in list(root.rglob("*")):
        if path.is_symlink() or path.is_file():
            if _forbidden_file(path) or path.name.lower() in {"headers"}:
                path.unlink(missing_ok=True)
        elif path.is_dir() and (path.name.lower() in FORBIDDEN_DIR_NAMES or path.name == "Headers"):
            shutil.rmtree(path, ignore_errors=True)


def _copy_framework(src: Path, dest: Path) -> None:
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(src, dest, symlinks=True)
    _purge_forbidden(dest)


def copy_runtime_tree(src: Path, dest: Path) -> None:
    """Copy dynamic libraries from *src* into *dest*. Existing dest is replaced."""
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True)
    if not src.is_dir():
        raise SystemExit(f"runtime directory missing: {src.name}")

    def visit(directory: Path, target: Path) -> None:
        target.mkdir(parents=True, exist_ok=True)
        for item in directory.iterdir():
            if is_macos_junk_name(item.name):
                continue
            if item.name.lower() in FORBIDDEN_DIR_NAMES or item.name == "Headers":
                continue
            if item.is_dir() and item.suffix == ".framework":
                _copy_framework(item, target / item.name)
                continue
            if item.is_symlink() or item.is_file():
                if is_dynamic_library(item):
                    shutil.copy2(item, target / item.name, follow_symlinks=False)
                continue
            if item.is_dir():
                # Keep one level of nesting only when it holds dynamic libraries
                # (a redistributable subfolder). Do not walk samples or docs.
                visit(item, target / item.name)
                if target.joinpath(item.name).is_dir() and not any(target.joinpath(item.name).rglob("*")):
                    shutil.rmtree(target / item.name, ignore_errors=True)

    visit(src, dest)
    _purge_forbidden(dest)
    assert_runtime_only(dest)


def assert_runtime_only(dest: Path) -> None:
    leaked: list[str] = []
    for path in dest.rglob("*"):
        if path.is_dir() and (path.name.lower() in FORBIDDEN_DIR_NAMES or path.name == "Headers"):
            leaked.append(path.name)
        elif path.is_file() and _forbidden_file(path):
            leaked.append(path.name)
    if leaked:
        preview = ", ".join(leaked[:8])
        raise SystemExit(f"ERROR: non-runtime files in private directory ({len(leaked)}): {preview}")
