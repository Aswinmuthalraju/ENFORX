#!/usr/bin/env bash
# patch-armoriq.sh — Install / update the ArmorIQ OpenClaw plugin.
#
# Usage (from project root):
#   bash armoriq-openclaw-plugin/patch-armoriq.sh
#
# What it does:
#   1. Verifies ARMORIQ_API_KEY is set in .env
#   2. Links the Node.js plugin/ directory into OpenClaw
#   3. Restarts the OpenClaw gateway so the plugin is live
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

echo "[armoriq-patch] Project root: ${PROJECT_ROOT}"

# 1. Check for ARMORIQ_API_KEY
if [ -f "${PROJECT_ROOT}/.env" ]; then
    # shellcheck disable=SC1090
    set -a; source "${PROJECT_ROOT}/.env"; set +a
fi

if [ -z "${ARMORIQ_API_KEY:-}" ]; then
    echo "[armoriq-patch] ERROR: ARMORIQ_API_KEY is not set in .env" >&2
    exit 1
fi
echo "[armoriq-patch] ARMORIQ_API_KEY: ${ARMORIQ_API_KEY:0:12}..."

# 2. Install Node plugin into OpenClaw
PLUGIN_DIR="${PROJECT_ROOT}/plugin"
if [ ! -d "${PLUGIN_DIR}" ]; then
    echo "[armoriq-patch] ERROR: plugin/ directory not found at ${PLUGIN_DIR}" >&2
    exit 1
fi

if command -v openclaw &>/dev/null; then
    echo "[armoriq-patch] Linking plugin into OpenClaw..."
    openclaw plugins install --link "${PLUGIN_DIR}"
    echo "[armoriq-patch] Plugin installed."
else
    echo "[armoriq-patch] WARNING: 'openclaw' CLI not found — skipping plugin install."
    echo "                Install OpenClaw and re-run this script."
fi

# 3. Restart gateway if running
if command -v openclaw &>/dev/null; then
    echo "[armoriq-patch] Restarting OpenClaw gateway..."
    openclaw gateway restart 2>/dev/null || openclaw gateway start 2>/dev/null || true
fi

echo "[armoriq-patch] Done."
