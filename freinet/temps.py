"""Temps : instants UTC en ISO 8601 (#55) et date logique dans le fuseau de l'élève (#54)."""

from __future__ import annotations

from datetime import UTC, date, datetime
from zoneinfo import ZoneInfo


def _exiger_fuseau(instant: datetime) -> None:
    if instant.tzinfo is None:
        raise ValueError(f"instant sans fuseau : {instant!r} (toujours un datetime aware)")


def maintenant() -> datetime:
    """L'instant présent, en UTC."""
    return datetime.now(UTC)


def vers_iso(instant: datetime) -> str:
    """Sérialise un instant en ISO 8601 UTC (`...+00:00`)."""
    _exiger_fuseau(instant)
    return instant.astimezone(UTC).isoformat()


def depuis_iso(texte: str) -> datetime:
    """Relit un horodatage ISO 8601 ; refuse un horodatage sans fuseau."""
    instant = datetime.fromisoformat(texte)
    _exiger_fuseau(instant)
    return instant.astimezone(UTC)


def date_logique(instant: datetime, fuseau: str) -> date:
    """Le jour du calendrier de l'élève à cet instant — graine de la sélection (inv. 6)."""
    _exiger_fuseau(instant)
    return instant.astimezone(ZoneInfo(fuseau)).date()
