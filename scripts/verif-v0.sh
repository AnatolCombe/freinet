#!/usr/bin/env bash
# Vérification V0 (PRD §5) : 0 si le scénario du matin tient de bout en bout (carte publiée,
# tickets, retour QR, FSRS, rejeu), que la suite est verte avec ≥ 85 % de couverture, que les
# index sont à jour (inv. 13) et que les contrats d'étape sont au format ICM (inv. 12).
set -euo pipefail
cd "$(dirname "$0")/.."
PY=".venv/bin/python"
export FREINET_SANS_LLM=1  # le ticket sort sans LLM (inv. 7)
export FREINET_SANS_RESEAU=1  # le ticket sort sans météo (inv. 7)
"$PY" scripts/verif_v0.py
"$PY" -m pytest -q
"$PY" scripts/regen-index.py --check
"$PY" scripts/verif-contrats.py
echo "V0 : vérification réussie"
