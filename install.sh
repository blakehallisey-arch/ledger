#!/usr/bin/env sh
# Puts a `ledger` command on your PATH. Nothing else is installed, nothing is
# downloaded, and the repo stays where you cloned it.
set -eu

REPO="$(cd "$(dirname "$0")" && pwd)"
BIN="${BIN:-$HOME/.local/bin}"

mkdir -p "$BIN"
cat > "$BIN/ledger" <<EOF
#!/usr/bin/env sh
exec python3 -m ledger "\$@"
EOF
chmod +x "$BIN/ledger"

echo "installed: $BIN/ledger"
echo "add to PATH if needed:  export PATH=\"\$PATH:$BIN\""
echo "and to PYTHONPATH:      export PYTHONPATH=\"\$PYTHONPATH:$REPO\""
