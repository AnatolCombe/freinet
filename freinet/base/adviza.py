"""Requêtes d'action de l'API ADVIZA déjà traitées (PROF-A3) : la partie de la couche SQLite
(inv. 1) qui les concerne. Mixin de `Base`, sur la connexion qu'elle ouvre. Ajout seul
(migration 004) : une réponse enregistrée ne change jamais."""

from __future__ import annotations

import sqlite3

from freinet.temps import maintenant, vers_iso


class RequetesAdviza:
    _conn: sqlite3.Connection

    def requete_adviza(self, brainiac_id: str, cle: str) -> tuple[str, str, str] | None:
        """(action, empreinte de la requête, réponse JSON) déjà enregistrées pour cette clé."""
        ligne = self._conn.execute(
            "SELECT action, empreinte, reponse FROM adviza_requete"
            " WHERE brainiac_id = ? AND cle = ?",
            (brainiac_id, cle),
        ).fetchone()
        return None if ligne is None else (str(ligne[0]), str(ligne[1]), str(ligne[2]))

    def enregistrer_requete_adviza(
        self, brainiac_id: str, cle: str, action: str, empreinte: str, reponse: str
    ) -> bool:
        """Enregistre la réponse ; `False` si la clé l'était déjà (la première reste). Vérifier
        puis insérer sous un seul verrou d'écriture : le trigger d'ajout seul refuserait même
        `INSERT OR IGNORE`."""
        self._conn.execute("BEGIN IMMEDIATE")
        try:
            existe = self._conn.execute(
                "SELECT 1 FROM adviza_requete WHERE brainiac_id = ? AND cle = ?",
                (brainiac_id, cle),
            ).fetchone()
            if existe is None:
                self._conn.execute(
                    "INSERT INTO adviza_requete"
                    " (brainiac_id, cle, action, empreinte, reponse, recue_le)"
                    " VALUES (?, ?, ?, ?, ?, ?)",
                    (brainiac_id, cle, action, empreinte, reponse, vers_iso(maintenant())),
                )
        except BaseException:
            self._conn.rollback()
            raise
        self._conn.commit()
        return existe is None
