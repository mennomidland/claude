#!/bin/bash
# Environment setup script for the `Midland` cloud environment.
#
# Paste the body of this file into: Edit cloud environment -> Setup script.
# It runs on every new session, BEFORE Claude Code launches.
#
# WHY THIS EXISTS
# ---------------
# A scheduled Routine fires a fresh session with no git source configured, so the
# session starts with an empty workspace and has to fetch the tool itself. Code
# that arrives *after* startup, pulled by the agent, is treated by the auto-mode
# permission classifier as "Code from External" and refused -- which made two
# consecutive fires of the scan-ingest Routine no-ops: the clone and branch were
# correct, but tools/scan_ingest.py was never allowed to execute.
#
# Cloning here instead means the checkout is part of the session's workspace at
# launch, exactly like an interactive session that was started from the repo.
#
# It is deliberately NOT a permission grant and writes no settings file. If the
# classifier still refuses after this, the answer is to stop wrapping the script
# in an agent at all -- see docs/routines/06-scan-mailbox.md.
set -euo pipefail

REPO_URL="https://github.com/mennomidland/claude.git"
BRANCH="claude/automation-mailbox-access-chviuj"
DEST="$HOME/claude"

if [ -d "$DEST/.git" ]; then
    # Already present (session resumed, or a previous setup run). Refresh it
    # rather than cloning over the top.
    git -C "$DEST" fetch --quiet origin "$BRANCH" || true
    git -C "$DEST" checkout --quiet "$BRANCH" || true
    git -C "$DEST" reset --hard --quiet "origin/$BRANCH" || true
else
    git clone --quiet --branch "$BRANCH" "$REPO_URL" "$DEST"
fi

# Fail loudly here rather than leaving a Routine to discover it at 3am.
test -f "$DEST/tools/scan_ingest.py" || {
    echo "SETUP FAILED: $DEST/tools/scan_ingest.py missing after clone" >&2
    exit 1
}

echo "setup: $DEST ready on $(git -C "$DEST" rev-parse --abbrev-ref HEAD) @ $(git -C "$DEST" rev-parse --short HEAD)"
