#!/usr/bin/env bash
# Mints the secrets, once. The admin key never leaves this machine's state
# directory and is never passed into a world container.
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"

mint() {
    local path="$STATE_DIR/$1"
    if [ -s "$path" ]; then
        log "$1 already exists"
    else
        python3 -c "import secrets; print(secrets.token_hex(24))" > "$path"
        chmod 600 "$path"
        log "minted $1"
    fi
}

mint caretaker-token
mint identity-world-key
mint identity-admin-key

# The one secret that cannot be minted here: it needs a browser.
if [ -s "$STATE_DIR/claude-token" ]; then
    log "claude-token already exists"
else
    log "claude-token is missing. Run 'claude setup-token' on a machine with a"
    log "browser and write the result to state/claude-token."
fi
