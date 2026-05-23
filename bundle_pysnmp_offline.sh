#!/usr/bin/env bash
# bundle_pysnmp_offline.sh
# ========================
# Run this on a machine WITH internet access (your laptop).
# It downloads pysnmp 7.1.16 and all its dependencies as .whl files
# into a folder you can copy to your air-gapped work environment.
#
# Usage (on laptop with internet):
#   bash bundle_pysnmp_offline.sh
#
# Then copy the "pysnmp_offline_bundle/" folder to your work machine via USB
# or secure file transfer.
#
# Install on air-gapped work machine:
#   pip install --no-index --find-links=pysnmp_offline_bundle pysnmp==7.1.16

set -euo pipefail

BUNDLE_DIR="pysnmp_offline_bundle"
PYSNMP_VERSION="7.1.16"

echo "==> Creating bundle directory: $BUNDLE_DIR"
mkdir -p "$BUNDLE_DIR"

echo "==> Downloading pysnmp $PYSNMP_VERSION and all dependencies..."
pip download \
    "pysnmp==$PYSNMP_VERSION" \
    pytest \
    --dest "$BUNDLE_DIR" \
    --platform manylinux_2_17_x86_64 \
    --python-version 311 \
    --only-binary=:all: \
    --no-deps 2>/dev/null || true

# Also download with deps resolved
pip download \
    "pysnmp==$PYSNMP_VERSION" \
    pytest \
    --dest "$BUNDLE_DIR"

echo ""
echo "==> Bundle contents:"
ls -lh "$BUNDLE_DIR"

echo ""
echo "==> Done. Transfer the '$BUNDLE_DIR' folder to your work machine."
echo ""
echo "    On the work machine, install with:"
echo "    pip install --no-index --find-links=$BUNDLE_DIR pysnmp==$PYSNMP_VERSION"
echo "    pip install --no-index --find-links=$BUNDLE_DIR pytest"
