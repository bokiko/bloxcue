#!/bin/sh
# Compatibility shim for v2 shell-hook installs. New installs use
# hooks/memory-retrieve.py directly.
SCRIPT_DIR=$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd)
exec python3 "$SCRIPT_DIR/memory-retrieve.py"
