#!/usr/bin/env bash
set -euo pipefail
# Usage: ./scripts/encode_google_sa_json_b64.sh /path/to/service_account.json
base64 -w 0 "$1"
echo
