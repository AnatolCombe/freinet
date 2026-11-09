#!/usr/bin/env bash
# Installe (ou retire, avec --retirer) les agents launchd du rituel du matin (#53).
# Ne touche qu'à ~/Library/LaunchAgents ; le réveil du Mac (pmset, sudo) reste à lancer soi-même.
set -euo pipefail
cd "$(dirname "$0")/.."
if [[ "${1:-}" == "--retirer" ]]; then
  exec .venv/bin/python -m freinet.launchd desinstaller
fi
exec .venv/bin/python -m freinet.launchd installer
