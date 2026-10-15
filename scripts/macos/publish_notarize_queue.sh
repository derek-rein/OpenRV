#!/bin/bash
# Upload the signed DMG and its notarization record to the draft release
# `notarize-queue`. The Ubuntu workflow notarize-finish.yml is the only
# consumer. A missing record (unsigned build, or the opt-in macOS wait path)
# is a no-op.

set -euo pipefail

JSON_PATH="${1:-dist/notarize-pending.json}"
QUEUE_TAG="${NOTARIZE_QUEUE_TAG:-notarize-queue}"

if [[ ! -f "${JSON_PATH}" ]]; then
  echo "No ${JSON_PATH}; notarization queue unchanged."
  exit 0
fi

if [[ -z "${GH_TOKEN:-}" && -z "${GITHUB_TOKEN:-}" ]]; then
  echo "ERROR: GH_TOKEN is required to publish the notarization queue." >&2
  exit 1
fi
export GH_TOKEN="${GH_TOKEN:-${GITHUB_TOKEN}}"

if [[ -z "${GITHUB_REPOSITORY:-}" ]]; then
  echo "ERROR: GITHUB_REPOSITORY is required." >&2
  exit 1
fi
export GH_REPO="${GITHUB_REPOSITORY}"

read_field() {
  python3 -c 'import json,sys; print(json.load(open(sys.argv[1], encoding="utf-8"))[sys.argv[2]])' "${JSON_PATH}" "$1"
}

submission_id=$(read_field submission_id)
dmg_name=$(read_field dmg_name)
if [[ ! "${submission_id}" =~ ^[A-Za-z0-9-]+$ ]]; then
  echo "ERROR: unexpected submission id: ${submission_id}" >&2
  exit 1
fi
if [[ "${dmg_name}" == *"/"* || "${dmg_name}" == *".."* ]]; then
  echo "ERROR: unexpected dmg name: ${dmg_name}" >&2
  exit 1
fi

dist_dir=$(cd "$(dirname "${JSON_PATH}")" && pwd)
dmg_path="${dist_dir}/${dmg_name}"
if [[ ! -f "${dmg_path}" ]]; then
  echo "ERROR: DMG not found at ${dmg_path}" >&2
  exit 1
fi

work=$(mktemp -d)
trap 'rm -rf "${work}"' EXIT
cp "${JSON_PATH}" "${work}/pending-${submission_id}.json"
cp "${dmg_path}" "${work}/pending-${submission_id}.dmg"

if ! gh release view "${QUEUE_TAG}" >/dev/null 2>&1; then
  if [[ -z "${GITHUB_SHA:-}" ]]; then
    echo "ERROR: GITHUB_SHA is required to create the ${QUEUE_TAG} draft release." >&2
    exit 1
  fi
  gh release create "${QUEUE_TAG}" \
    --draft \
    --title "Notarization queue" \
    --notes "Pending Apple notarization submissions. notarize-finish.yml consumes pending-*.json assets. Do not publish this draft." \
    --target "${GITHUB_SHA}"
fi

gh release upload "${QUEUE_TAG}" \
  "${work}/pending-${submission_id}.json" \
  "${work}/pending-${submission_id}.dmg" \
  --clobber

echo "Queued submission ${submission_id} on draft release ${QUEUE_TAG}."
if [[ -n "${GITHUB_STEP_SUMMARY:-}" ]]; then
  printf 'Notarization submitted: %s. Stapling continues on the Ubuntu Notarize finish workflow.\n' "${submission_id}" >>"${GITHUB_STEP_SUMMARY}"
fi
