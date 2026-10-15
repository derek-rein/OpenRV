#!/bin/bash
# Sign RV.app (inside-out), wrap it in a DMG, and submit that DMG for notarization.
#
# Signing identity is fixed to the company Developer ID. A personal identity in
# MACOS_SIGNING_IDENTITY is a hard error. When the Apple secrets are absent the
# script still writes an unsigned DMG and exits 0 so fork PRs and unconfigured
# dispatches produce an artifact.
#
# `notarytool submit` is called without --wait. The default path writes
# dist/notarize-pending.json and returns so the macOS runner is not held for
# Apple's analysis. Stapling runs later on ubuntu via scripts/macos/notarize_finish.py.
#
# WAIT_FOR_NOTARIZATION=true restores the old in-job poll (up to 4 hours),
# stapler, and spctl. The release workflow leaves that off.

set -euo pipefail

INSTALL_PREFIX="${1:-_install}"
OUTPUT_DIR="${2:-dist}"
DMG_NAME="${DMG_NAME:-openrv-macos-arm64.dmg}"
EXPECTED_IDENTITY="Developer ID Application: Medeu Global LLC (83546T4BT8)"
EXPECTED_TEAM="83546T4BT8"
MAX_WAIT_SECONDS=$((4 * 60 * 60))

SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
ENTITLEMENTS="${SCRIPT_DIR}/entitlements.plist"

KEYCHAIN=""
P12_FILE=""
P8_KEY=""
KEYCHAIN_PASSWORD=""
PREVIOUS_DEFAULT_KEYCHAIN=""

log() {
  printf '%s %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$*"
}

cleanup() {
  if [[ -n "${PREVIOUS_DEFAULT_KEYCHAIN}" ]]; then
    security default-keychain -s "${PREVIOUS_DEFAULT_KEYCHAIN}" >/dev/null 2>&1 || true
  fi
  if [[ -n "${KEYCHAIN}" ]]; then
    security delete-keychain "${KEYCHAIN}" >/dev/null 2>&1 || true
  fi
  if [[ -n "${P12_FILE}" ]]; then
    rm -f "${P12_FILE}"
  fi
  if [[ -n "${P8_KEY}" ]]; then
    rm -f "${P8_KEY}"
  fi
}
trap cleanup EXIT

require_identity() {
  if [[ -n "${MACOS_SIGNING_IDENTITY:-}" && "${MACOS_SIGNING_IDENTITY}" != "${EXPECTED_IDENTITY}" ]]; then
    log "ERROR: MACOS_SIGNING_IDENTITY must be exactly: ${EXPECTED_IDENTITY}"
    log "Refusing to sign with any other identity, including a personal Apple ID."
    exit 1
  fi
  if [[ -n "${APPLE_TEAM_ID:-}" && "${APPLE_TEAM_ID}" != "${EXPECTED_TEAM}" ]]; then
    log "ERROR: APPLE_TEAM_ID must be ${EXPECTED_TEAM} (Medeu Global LLC)."
    exit 1
  fi
}

secrets_present() {
  [[ -n "${MACOS_CERT_P12_BASE64:-}" \
    && -n "${MACOS_CERT_PASSWORD:-}" \
    && -n "${MACOS_SIGNING_IDENTITY:-}" \
    && -n "${APPLE_TEAM_ID:-}" \
    && -n "${ASC_KEY_ID:-}" \
    && -n "${ASC_ISSUER_ID:-}" \
    && -n "${ASC_API_KEY_P8:-}" ]]
}

wait_requested() {
  case "${WAIT_FOR_NOTARIZATION:-}" in
    1 | true | TRUE | yes | YES)
      return 0
      ;;
    *)
      return 1
      ;;
  esac
}

missing_secret_names() {
  if [[ -z "${MACOS_CERT_P12_BASE64:-}" ]]; then printf '%s\n' "MACOS_CERT_P12_BASE64"; fi
  if [[ -z "${MACOS_CERT_PASSWORD:-}" ]]; then printf '%s\n' "MACOS_CERT_PASSWORD"; fi
  if [[ -z "${MACOS_SIGNING_IDENTITY:-}" ]]; then printf '%s\n' "MACOS_SIGNING_IDENTITY"; fi
  if [[ -z "${APPLE_TEAM_ID:-}" ]]; then printf '%s\n' "APPLE_TEAM_ID"; fi
  if [[ -z "${ASC_KEY_ID:-}" ]]; then printf '%s\n' "ASC_KEY_ID"; fi
  if [[ -z "${ASC_ISSUER_ID:-}" ]]; then printf '%s\n' "ASC_ISSUER_ID"; fi
  if [[ -z "${ASC_API_KEY_P8:-}" ]]; then printf '%s\n' "ASC_API_KEY_P8"; fi
}

find_app() {
  if [[ -d "${INSTALL_PREFIX}/RV.app" ]]; then
    printf '%s\n' "${INSTALL_PREFIX}/RV.app"
    return 0
  fi
  find "${INSTALL_PREFIX}" -type d -name 'RV.app' -print -quit
}

create_dmg() {
  local app_path="$1"
  local dmg_path="$2"
  local stage
  stage=$(mktemp -d)
  rm -f "${dmg_path}"
  cp -R "${app_path}" "${stage}/"
  ln -s /Applications "${stage}/Applications"
  hdiutil create \
    -volname "Open RV" \
    -srcfolder "${stage}" \
    -ov \
    -format UDZO \
    "${dmg_path}"
  rm -rf "${stage}"
}

is_macho() {
  local desc
  desc=$(file -b "$1" 2>/dev/null || true)
  case "${desc}" in
    Mach-O*)
      return 0
      ;;
    *)
      return 1
      ;;
  esac
}

is_macho_executable() {
  local desc
  desc=$(file -b "$1" 2>/dev/null || true)
  case "${desc}" in
    Mach-O*executable*)
      return 0
      ;;
    *)
      return 1
      ;;
  esac
}

sign_one() {
  local target="$1"
  local use_entitlements="$2"
  if [[ "${use_entitlements}" == "yes" ]]; then
    codesign --force --options runtime --timestamp \
      --entitlements "${ENTITLEMENTS}" \
      --sign "${EXPECTED_IDENTITY}" \
      "${target}"
  else
    codesign --force --options runtime --timestamp \
      --sign "${EXPECTED_IDENTITY}" \
      "${target}"
  fi
}

# Deepest path first so nested plugins are signed before their parent bundle.
sign_inside_out() {
  local app_path="$1"
  local list path use_ent inplace
  list=$(mktemp)

  # 1. Get every non-Mach-O regular file out of Contents/MacOS, PlugIns and
  #    Frameworks (moved to Contents/Resources + symlink). The few that must
  #    stay (scripts RV executes next to its binary) are signed in place here,
  #    before any Mach-O or bundle, so the parent seals see them signed.
  inplace=$(mktemp)
  python3 "${SCRIPT_DIR}/relocate_nonmacho.py" "${app_path}" >"${inplace}"
  while IFS= read -r -d '' path; do
    log "codesign non-Mach-O in place ${path}"
    sign_one "${path}" "no"
  done <"${inplace}"
  rm -f "${inplace}"

  # 2. Mach-O files, deepest path first. Never --deep.

  find "${app_path}" -type f ! -path '*.dSYM/*' -print0 |
    python3 -c '
import sys
raw = sys.stdin.buffer.read().split(b"\0")
paths = [p.decode("utf-8", "surrogateescape") for p in raw if p]
paths.sort(key=lambda p: (p.count("/"), len(p)), reverse=True)
if paths:
    sys.stdout.buffer.write(b"\0".join(p.encode("utf-8", "surrogateescape") for p in paths) + b"\0")
' >"${list}"

  while IFS= read -r -d '' path; do
    if ! is_macho "${path}"; then
      continue
    fi
    use_ent="no"
    if is_macho_executable "${path}"; then
      use_ent="yes"
    fi
    log "codesign ${path}"
    sign_one "${path}" "${use_ent}"
  done <"${list}"
  rm -f "${list}"

  list=$(mktemp)
  find "${app_path}" -type d \
    \( -name '*.framework' -o -name '*.app' -o -name '*.bundle' -o -name '*.xpc' -o -name '*.plugin' \) \
    ! -path "${app_path}" -print0 |
    python3 -c '
import sys
raw = sys.stdin.buffer.read().split(b"\0")
paths = [p.decode("utf-8", "surrogateescape") for p in raw if p]
paths.sort(key=lambda p: (p.count("/"), len(p)), reverse=True)
if paths:
    sys.stdout.buffer.write(b"\0".join(p.encode("utf-8", "surrogateescape") for p in paths) + b"\0")
' >"${list}"

  while IFS= read -r -d '' path; do
    log "codesign bundle ${path}"
    sign_one "${path}" "yes"
  done <"${list}"
  rm -f "${list}"

  log "codesign app ${app_path}"
  sign_one "${app_path}" "yes"
  verify_app "${app_path}"
}

# Fail here, before the DMG and notarytool, if anything is unsealed.
verify_app() {
  local app_path="$1" out
  log "codesign --verify --deep --strict ${app_path}"
  codesign --verify --deep --strict --verbose=2 "${app_path}"
  log "spctl --assess --type execute ${app_path}"
  out=$(spctl --assess --type execute --verbose=4 "${app_path}" 2>&1 || true)
  log "${out}"
  # Before notarization Gatekeeper reports "Unnotarized Developer ID"; that is
  # expected here. Anything else (bad signature, wrong identity) is fatal.
  case "${out}" in
    *": accepted"* | *"Unnotarized Developer ID"*) ;;
    *)
      log "ERROR: spctl rejected ${app_path} for a reason other than missing notarization"
      exit 1
      ;;
  esac
}

import_certificate() {
  local work
  work=$(mktemp -d)
  P12_FILE="${work}/certificate.p12"
  KEYCHAIN="${work}/openrv-signing.keychain-db"
  KEYCHAIN_PASSWORD=$(python3 -c 'import secrets; print(secrets.token_hex(16))')
  PREVIOUS_DEFAULT_KEYCHAIN=$(security default-keychain 2>/dev/null | sed -e 's/^[[:space:]]*"//' -e 's/"[[:space:]]*$//' || true)
  python3 -c 'import base64, os, sys; open(sys.argv[1], "wb").write(base64.b64decode(os.environ["MACOS_CERT_P12_BASE64"]))' "${P12_FILE}"
  security create-keychain -p "${KEYCHAIN_PASSWORD}" "${KEYCHAIN}"
  security set-keychain-settings -lut 21600 "${KEYCHAIN}"
  security unlock-keychain -p "${KEYCHAIN_PASSWORD}" "${KEYCHAIN}"
  # Search list and default keychain must include the temp keychain before
  # set-key-partition-list, or codesign from a CI runner cannot use the key.
  security list-keychains -d user -s "${KEYCHAIN}"
  security default-keychain -s "${KEYCHAIN}"
  security import "${P12_FILE}" -k "${KEYCHAIN}" -P "${MACOS_CERT_PASSWORD}" -T /usr/bin/codesign -T /usr/bin/security -f pkcs12
  security set-key-partition-list -S apple-tool:,apple:,codesign: -s -k "${KEYCHAIN_PASSWORD}" "${KEYCHAIN}" >/dev/null
  if ! security find-identity -v -p codesigning "${KEYCHAIN}" | grep -F "Developer ID Application" | grep -F "Medeu Global LLC" | grep -F "${EXPECTED_TEAM}" >/dev/null; then
    log "ERROR: imported certificate is not ${EXPECTED_IDENTITY}"
    security find-identity -v -p codesigning "${KEYCHAIN}" || true
    exit 1
  fi
}

poll_notarization() {
  local submission_id="$1"
  local started deadline sleep_for info_json status elapsed
  started=${SECONDS}
  deadline=$((SECONDS + MAX_WAIT_SECONDS))
  sleep_for=30
  while [[ "${SECONDS}" -lt "${deadline}" ]]; do
    info_json=$(xcrun notarytool info "${submission_id}" \
      --key "${P8_KEY}" \
      --key-id "${ASC_KEY_ID}" \
      --issuer "${ASC_ISSUER_ID}" \
      --output-format json)
    status=$(printf '%s' "${info_json}" | python3 -c 'import json,sys; data=json.load(sys.stdin); print(data.get("status") or "")')
    elapsed=$((SECONDS - started))
    log "notarytool info id=${submission_id} status=${status:-unknown} elapsed=${elapsed}s"
    log "${info_json}"
    case "${status}" in
      Accepted)
        return 0
        ;;
      Invalid | Rejected)
        log "Notarization ${status}. Fetching the notary log."
        xcrun notarytool log "${submission_id}" \
          --key "${P8_KEY}" \
          --key-id "${ASC_KEY_ID}" \
          --issuer "${ASC_ISSUER_ID}" || true
        return 1
        ;;
      *)
        sleep "${sleep_for}"
        if [[ "${sleep_for}" -lt 180 ]]; then
          sleep_for=$((sleep_for + 15))
        fi
        ;;
    esac
  done
  log "ERROR: notarization still ${status:-unknown} after ${MAX_WAIT_SECONDS}s"
  xcrun notarytool log "${submission_id}" \
    --key "${P8_KEY}" \
    --key-id "${ASC_KEY_ID}" \
    --issuer "${ASC_ISSUER_ID}" || true
  return 1
}

main() {
  local app dmg do_sign missing submission_json submission_id
  require_identity
  mkdir -p "${OUTPUT_DIR}"
  app=$(find_app || true)
  if [[ -z "${app}" || ! -d "${app}" ]]; then
    log "ERROR: RV.app not found under ${INSTALL_PREFIX}"
    exit 1
  fi
  log "Found ${app}"
  dmg="${OUTPUT_DIR}/${DMG_NAME}"

  do_sign=0
  if secrets_present; then
    do_sign=1
  else
    missing=$(missing_secret_names | tr '\n' ' ' || true)
    log "Skipping macOS signing and notarization; secrets not set:${missing:+ ${missing}}"
    log "Writing an unsigned DMG. Fork pull requests do not receive these secrets."
  fi

  if [[ "${do_sign}" -eq 1 ]]; then
    if [[ ! -f "${ENTITLEMENTS}" ]]; then
      log "ERROR: missing entitlements plist ${ENTITLEMENTS}"
      exit 1
    fi
    import_certificate
    sign_inside_out "${app}"
    create_dmg "${app}" "${dmg}"
    log "codesign dmg ${dmg}"
    codesign --force --timestamp --sign "${EXPECTED_IDENTITY}" "${dmg}"

    P8_KEY=$(mktemp)
    umask 077
    printf '%s\n' "${ASC_API_KEY_P8}" >"${P8_KEY}"
    chmod 600 "${P8_KEY}"

    log "Submitting ${dmg} to notarytool (no --wait)"
    submission_json=$(xcrun notarytool submit "${dmg}" \
      --key "${P8_KEY}" \
      --key-id "${ASC_KEY_ID}" \
      --issuer "${ASC_ISSUER_ID}" \
      --output-format json)
    log "${submission_json}"
    submission_id=$(printf '%s' "${submission_json}" | python3 -c 'import json,sys; data=json.load(sys.stdin); print(data.get("id") or "")')
    if [[ -z "${submission_id}" ]]; then
      log "ERROR: notarytool submit did not return an id"
      exit 1
    fi
    if wait_requested; then
      log "WAIT_FOR_NOTARIZATION is set; polling on this macOS runner (this holds the runner)."
      poll_notarization "${submission_id}"
      log "Stapling ${dmg}"
      xcrun stapler staple "${dmg}"
      if xcrun stapler staple "${app}"; then
        log "Stapled ${app}"
      else
        log "WARNING: stapler could not staple ${app}; the DMG ticket is the one that ships"
      fi
      log "spctl ${dmg}"
      spctl --assess --verbose=4 --type open --context context:primary-signature "${dmg}"
      if spctl --assess --verbose=4 --type execute "${app}"; then
        log "spctl accepted ${app}"
      else
        log "WARNING: spctl execute assessment of ${app} did not pass; DMG assessment did"
      fi
      log "Signed and notarized ${dmg} on this runner"
    else
      python3 "${SCRIPT_DIR}/notarize_finish.py" write-record \
        --output "${OUTPUT_DIR}/notarize-pending.json" \
        --submission-id "${submission_id}" \
        --dmg "${dmg}" \
        --dmg-name "${DMG_NAME}"
      log "Submitted ${submission_id}. Not waiting on this macOS runner."
      log "Pending record: ${OUTPUT_DIR}/notarize-pending.json"
    fi
  else
    create_dmg "${app}" "${dmg}"
    log "Unsigned DMG written to ${dmg}"
  fi
}

main "$@"
