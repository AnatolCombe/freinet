"""Plans du jour et accès du QR : la partie de la couche SQLite (inv. 1) qui les concerne.

Mixin de `Base`, sur la connexion qu'elle ouvre. Un plan par élève et par jour logique ; son
statut avance de `planifie` à `imprime` (ticket remis) puis `note` (au moins un retour du QR).
"""

from __future__ import annotations

import sqlite3
import uuid
from dataclasses import dataclass
from datetime import date

from freinet.temps import maintenant, vers_iso


def _exiger_jour(jour: date) -> None:
    """Un jour logique, jamais un instant : un `datetime` donnerait une autre clé en base."""
    if type(jour) is not date:
        raise TypeError(f"jour logique attendu (date), reçu {type(jour).__name__}")


@dataclass(frozen=True)
class PlanAcces:
    """Le plan qu'ouvre un jeton ou un code court (page du QR)."""

    plan_id: str
    brainiac_id: str
    jour: date
    nouvelle: str | None
    joker: bool


_COLONNES_ACCES = "plan_id, brainiac_id, date_logique, nouvelle, joker"


def _plan_acces(ligne: tuple[str, str, str, str | None, int] | None) -> PlanAcces | None:
    if ligne is None:
        return None
    return PlanAcces(ligne[0], ligne[1], date.fromisoformat(ligne[2]), ligne[3], ligne[4] == 1)


class PlansDuJour:
    _conn: sqlite3.Connection

    def plan_du_jour(self, brainiac_id: str, jour: date, nouvelle: str | None = None) -> str:
        """L'identifiant du plan de ce jour logique, créé au besoin (idempotent) ; `nouvelle`
        garde la notion présentée ce jour-là, et un appel sans `nouvelle` ne l'efface pas."""
        conserver = "COALESCE(excluded.nouvelle, plan_du_jour.nouvelle)"
        return self._plan(brainiac_id, jour, nouvelle, conserver)

    def fixer_plan(self, brainiac_id: str, jour: date, nouvelle: str | None) -> str:
        """Comme `plan_du_jour`, mais la notion enregistrée devient exactement `nouvelle`
        (même `None`) : la base suit ce qu'affiche le fichier du plan, qui fait foi."""
        return self._plan(brainiac_id, jour, nouvelle, "excluded.nouvelle")

    def _plan(self, brainiac_id: str, jour: date, nouvelle: str | None, valeur: str) -> str:
        _exiger_jour(jour)
        with self._conn:
            self._conn.execute(
                "INSERT INTO plan_du_jour"
                " (plan_id, brainiac_id, date_logique, statut, cree_le, nouvelle)"
                " VALUES (?, ?, ?, 'planifie', ?, ?)"
                f" ON CONFLICT (brainiac_id, date_logique) DO UPDATE SET nouvelle = {valeur}",
                (
                    str(uuid.uuid4()),
                    brainiac_id,
                    jour.isoformat(),
                    vers_iso(maintenant()),
                    nouvelle,
                ),
            )
        (plan_id,) = self._conn.execute(
            "SELECT plan_id FROM plan_du_jour WHERE brainiac_id = ? AND date_logique = ?",
            (brainiac_id, jour.isoformat()),
        ).fetchone()
        return str(plan_id)

    def marquer_imprime(self, brainiac_id: str, jour: date) -> None:
        """Le ticket de ce jour est sorti : sa notion compte désormais comme présentée. Un plan
        déjà noté (`note`) le reste. Sans plan pour ce jour, rien ne change."""
        _exiger_jour(jour)
        with self._conn:
            self._conn.execute(
                "UPDATE plan_du_jour SET statut = 'imprime'"
                " WHERE brainiac_id = ? AND date_logique = ? AND statut = 'planifie'",
                (brainiac_id, jour.isoformat()),
            )

    def concepts_presentes(self, brainiac_id: str, avant: date) -> dict[str, date]:
        """Les notions nouvelles des tickets remis (imprimés ou notés) avant le jour logique
        `avant`, chacune avec le premier jour où elle a été présentée. Un plan jamais imprimé
        (imprimante éteinte) ne compte pas : la notion sera reproposée."""
        _exiger_jour(avant)
        lignes = self._conn.execute(
            "SELECT nouvelle, MIN(date_logique) FROM plan_du_jour"
            " WHERE brainiac_id = ? AND date_logique < ? AND nouvelle IS NOT NULL"
            " AND statut IN ('imprime', 'note')"
            " GROUP BY nouvelle",
            (brainiac_id, avant.isoformat()),
        )
        return {concept: date.fromisoformat(jour) for concept, jour in lignes}

    def attribuer_acces(
        self, brainiac_id: str, jour: date, jeton_hache: str, code_hache: str
    ) -> None:
        """Le jeton du QR et le code court de ce plan, hachés (A1) ; remplace les précédents."""
        _exiger_jour(jour)
        with self._conn:
            curseur = self._conn.execute(
                "UPDATE plan_du_jour SET jeton_hache = ?, code_hache = ?"
                " WHERE brainiac_id = ? AND date_logique = ?",
                (jeton_hache, code_hache, brainiac_id, jour.isoformat()),
            )
        if curseur.rowcount != 1:
            raise LookupError(f"aucun plan le {jour.isoformat()} pour cet élève")

    def acces_du_plan(self, brainiac_id: str, jour: date) -> tuple[str | None, str | None]:
        """(jeton haché, code haché) du plan, `None` tant qu'aucun n'est attribué."""
        _exiger_jour(jour)
        ligne = self._conn.execute(
            "SELECT jeton_hache, code_hache FROM plan_du_jour"
            " WHERE brainiac_id = ? AND date_logique = ?",
            (brainiac_id, jour.isoformat()),
        ).fetchone()
        return (ligne[0], ligne[1]) if ligne else (None, None)

    def plan_par_acces(self, hache: str, depuis: date) -> PlanAcces | None:
        """Le plan dont le jeton ou le code court a ce haché, s'il date au plus tôt de `depuis`
        (un accès expiré n'ouvre plus rien)."""
        _exiger_jour(depuis)
        ligne = self._conn.execute(
            f"SELECT {_COLONNES_ACCES} FROM plan_du_jour"
            " WHERE (jeton_hache = ? OR code_hache = ?) AND date_logique >= ?",
            (hache, hache, depuis.isoformat()),
        ).fetchone()
        return _plan_acces(ligne)

    def plan_de(self, brainiac_id: str, jour: date) -> PlanAcces | None:
        """Le plan de cet élève ce jour logique (API ADVIZA : l'élève vient de son jeton)."""
        _exiger_jour(jour)
        ligne = self._conn.execute(
            f"SELECT {_COLONNES_ACCES} FROM plan_du_jour"
            " WHERE brainiac_id = ? AND date_logique = ?",
            (brainiac_id, jour.isoformat()),
        ).fetchone()
        return _plan_acces(ligne)

    def marquer_note(self, plan_id: str, joker: bool = False) -> None:
        """Un retour est arrivé par le QR : le plan passe à `note` (et garde le joker)."""
        with self._conn:
            self._conn.execute(
                "UPDATE plan_du_jour SET statut = 'note', joker = MAX(joker, ?) WHERE plan_id = ?",
                (int(joker), plan_id),
            )

    def concepts_joker(self, brainiac_id: str, avant: date) -> set[str]:
        """Notions déclarées « je sais déjà » (#26) sur un ticket antérieur à `avant`."""
        _exiger_jour(avant)
        lignes = self._conn.execute(
            "SELECT DISTINCT nouvelle FROM plan_du_jour WHERE brainiac_id = ?"
            " AND date_logique < ? AND joker = 1 AND nouvelle IS NOT NULL",
            (brainiac_id, avant.isoformat()),
        )
        return {concept for (concept,) in lignes}

    def tickets_notes(self, brainiac_id: str, du: date, au: date) -> int:
        """Tickets notés par le QR entre `du` et `au` inclus (objectif hebdomadaire, #9)."""
        _exiger_jour(du)
        _exiger_jour(au)
        (nombre,) = self._conn.execute(
            "SELECT COUNT(*) FROM plan_du_jour WHERE brainiac_id = ? AND statut = 'note'"
            " AND date_logique BETWEEN ? AND ?",
            (brainiac_id, du.isoformat(), au.isoformat()),
        ).fetchone()
        return int(nombre)

    def statut_du_plan(self, brainiac_id: str, jour: date) -> str | None:
        """`planifie`, `imprime` ou `note` ; `None` sans plan ce jour-là (heartbeat, #44)."""
        _exiger_jour(jour)
        ligne = self._conn.execute(
            "SELECT statut FROM plan_du_jour WHERE brainiac_id = ? AND date_logique = ?",
            (brainiac_id, jour.isoformat()),
        ).fetchone()
        return str(ligne[0]) if ligne else None
