"""La couche SQLite (inv. 1) : seul le paquet `freinet/base/` importe sqlite3 et exécute du
SQL. Il reçoit et rend des objets de `modele`. Ici la connexion, les migrations, le journal et
les caches ; `plans.py` : les plans du jour et les accès du QR (mixin de `Base`) ; `adviza.py` :
les requêtes de l'API ADVIZA déjà traitées."""

from __future__ import annotations

import sqlite3
import time
import uuid
from collections.abc import Callable, Iterable
from pathlib import Path
from types import TracebackType

from freinet.base.adviza import RequetesAdviza
from freinet.base.plans import PlansDuJour
from freinet.modele import Brainiac, EtatConcept, Inscription, Revue
from freinet.temps import depuis_iso, maintenant, vers_iso

MIGRATIONS = Path(__file__).resolve().parents[2] / "migrations"
EN_MEMOIRE = ":memory:"
ErreurSQLite = sqlite3.Error  # exposée pour que les appelants n'importent pas sqlite3 (inv. 1)
ATTENTE_VERROU_S = 30.0


def _ligne_revue(revue: Revue) -> tuple[object, ...]:
    return (
        revue.revue_id,
        revue.brainiac_id,
        revue.concept_id,
        revue.question_id,
        revue.nature,
        revue.note,
        vers_iso(revue.repondu_le),
        vers_iso(revue.saisi_le),
        revue.canal,
        revue.plan_id,
        revue.corrige_id,
    )


class Base(PlansDuJour, RequetesAdviza):
    """Connexion à `data/freinet.db`, migrée à l'ouverture."""

    def __init__(self, chemin: Path | str) -> None:
        if chemin != EN_MEMOIRE:
            Path(chemin).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(chemin, timeout=ATTENTE_VERROU_S)
        try:
            self._conn.execute("PRAGMA foreign_keys = ON")
            self._passer_en_wal()
            self._migrer()
        except BaseException:
            self._conn.close()
            raise

    def __enter__(self) -> Base:
        return self

    def __exit__(
        self,
        type_: type[BaseException] | None,
        valeur: BaseException | None,
        trace: TracebackType | None,
    ) -> None:
        self.fermer()

    def fermer(self) -> None:
        self._conn.close()

    def _passer_en_wal(self) -> None:
        """Le passage en WAL n'attend pas le verrou (pas de busy handler) : on réessaie."""
        limite = time.monotonic() + ATTENTE_VERROU_S
        while True:
            try:
                self._conn.execute("PRAGMA journal_mode = WAL")
                return
            except sqlite3.OperationalError:
                if time.monotonic() > limite:
                    raise
                time.sleep(0.05)

    def _versions(self) -> set[int]:
        return {v for (v,) in self._conn.execute("SELECT version FROM schema_version")}

    def _migrer(self) -> None:
        """Applique les migrations manquantes. Sûr si plusieurs processus ouvrent la base
        en même temps (page QR + passage quotidien) : chaque migration prend le verrou
        d'écriture (BEGIN IMMEDIATE) ; celui qui arrive second échoue, annule, relit
        `schema_version` et continue si l'autre l'a déjà appliquée."""
        with self._conn:
            self._conn.execute(
                "CREATE TABLE IF NOT EXISTS schema_version "
                "(version INTEGER PRIMARY KEY, applique_le TEXT NOT NULL)"
            )
        for fichier in sorted(MIGRATIONS.glob("[0-9][0-9][0-9]_*.sql")):
            version = int(fichier.name[:3])
            if version in self._versions():
                continue
            sql = fichier.read_text(encoding="utf-8")
            try:
                self._conn.executescript(
                    f"BEGIN IMMEDIATE;\n{sql}\n"
                    f"INSERT INTO schema_version VALUES ({version}, '{vers_iso(maintenant())}');\n"
                    "COMMIT;"
                )
            except sqlite3.Error:
                self._conn.rollback()
                if version not in self._versions():
                    raise

    # --- introspection (tests d'invariants) ---

    def tables(self) -> list[str]:
        lignes = self._conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' ORDER BY name"
        )
        return [nom for (nom,) in lignes]

    def colonnes(self, table: str) -> list[str]:
        if table not in self.tables():
            raise ValueError(f"table inconnue : {table}")
        return [ligne[1] for ligne in self._conn.execute(f"PRAGMA table_info({table})")]

    # --- élèves ---

    def ajouter_brainiac(self, nom: str, fuseau: str) -> str:
        brainiac_id = str(uuid.uuid4())
        with self._conn:
            self._conn.execute(
                "INSERT INTO brainiac (brainiac_id, nom, fuseau, cree_le) VALUES (?, ?, ?, ?)",
                (brainiac_id, nom, fuseau, vers_iso(maintenant())),
            )
        return brainiac_id

    def brainiac_par_nom(self, nom: str) -> Brainiac | None:
        return self._brainiac("nom", nom)

    def brainiac(self, brainiac_id: str) -> Brainiac | None:
        return self._brainiac("brainiac_id", brainiac_id)

    def _brainiac(self, colonne: str, valeur: str) -> Brainiac | None:
        ligne = self._conn.execute(
            "SELECT brainiac_id, nom, fuseau, dosage_projets, dosage_declares, dosage_serendipite"
            f" FROM brainiac WHERE {colonne} = ?",  # colonne fixée par l'appelant, jamais saisie
            (valeur,),
        ).fetchone()
        if ligne is None:
            return None
        return Brainiac(ligne[0], ligne[1], ligne[2], (ligne[3], ligne[4], ligne[5]))

    def inscrire(self, brainiac_id: str, carte_id: str, quete_active: str | None) -> None:
        """Inscrit l'élève à une carte, ou change sa quête active ; réinscrire sans quête garde
        la quête en cours."""
        with self._conn:
            self._conn.execute(
                "INSERT INTO inscription (brainiac_id, carte_id, quete_active, inscrit_le)"
                " VALUES (?, ?, ?, ?) ON CONFLICT (brainiac_id, carte_id) DO UPDATE"
                " SET quete_active = COALESCE(excluded.quete_active, inscription.quete_active)",
                (brainiac_id, carte_id, quete_active, vers_iso(maintenant())),
            )

    def inscriptions(self, brainiac_id: str) -> list[Inscription]:
        lignes = self._conn.execute(
            "SELECT carte_id, quete_active FROM inscription WHERE brainiac_id = ?"
            " ORDER BY carte_id",
            (brainiac_id,),
        )
        return [Inscription(carte_id, quete) for carte_id, quete in lignes]

    def brainiacs(self) -> list[str]:
        lignes = self._conn.execute("SELECT brainiac_id FROM brainiac ORDER BY brainiac_id")
        return [brainiac_id for (brainiac_id,) in lignes]

    # --- journal ---

    def ajouter_revue(self, revue: Revue) -> None:
        with self._conn:
            self._conn.execute(
                "INSERT INTO revue (revue_id, brainiac_id, concept_id, question_id, nature, note,"
                " repondu_le, saisi_le, canal, plan_id, corrige_id)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                _ligne_revue(revue),
            )

    def ajouter_revue_unique(self, revue: Revue) -> bool:
        """Ajoute la revue sauf si son identifiant existe déjà (idempotence du QR : un double
        envoi ne crée pas de doublon). Vérifier puis insérer sous un seul verrou d'écriture
        (BEGIN IMMEDIATE) : le trigger d'ajout seul refuserait même `INSERT OR IGNORE`. Rend
        `True` si elle a été ajoutée."""
        self._conn.execute("BEGIN IMMEDIATE")
        try:
            existe = self._conn.execute(
                "SELECT 1 FROM revue WHERE revue_id = ?", (revue.revue_id,)
            ).fetchone()
            if existe is None:
                self._conn.execute(
                    "INSERT INTO revue (revue_id, brainiac_id, concept_id, question_id, nature,"
                    " note, repondu_le, saisi_le, canal, plan_id, corrige_id)"
                    " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    _ligne_revue(revue),
                )
        except BaseException:
            self._conn.rollback()
            raise
        self._conn.commit()
        return existe is None

    def revues(self, brainiac_id: str) -> list[Revue]:
        lignes = self._conn.execute(
            "SELECT revue_id, brainiac_id, concept_id, question_id, nature, note, repondu_le,"
            " saisi_le, canal, plan_id, corrige_id FROM revue WHERE brainiac_id = ?"
            " ORDER BY repondu_le, revue_id",
            (brainiac_id,),
        )
        return [
            Revue(
                revue_id=ligne[0],
                brainiac_id=ligne[1],
                concept_id=ligne[2],
                question_id=ligne[3],
                nature=ligne[4],
                note=ligne[5],
                repondu_le=depuis_iso(ligne[6]),
                saisi_le=depuis_iso(ligne[7]),
                canal=ligne[8],
                plan_id=ligne[9],
                corrige_id=ligne[10],
            )
            for ligne in lignes
        ]

    def concepts_references(self) -> set[str]:
        """Tous les concepts cités par le journal, tous élèves confondus (#20)."""
        lignes = self._conn.execute("SELECT DISTINCT concept_id FROM revue")
        return {identifiant for (identifiant,) in lignes}

    # --- caches recalculables ---

    def remplacer_etat(
        self, brainiac_id: str, calcul: Callable[[list[Revue]], list[EtatConcept]]
    ) -> list[EtatConcept]:
        """Lit le journal de l'élève et réécrit ses caches `fsrs` + `maitrise` sous un seul
        verrou d'écriture (BEGIN IMMEDIATE) : une revue ajoutée entre-temps ou un recalcul
        concurrent ne peut pas laisser des caches périmés (inv. 4)."""
        self._conn.execute("BEGIN IMMEDIATE")
        try:
            etats = calcul(self.revues(brainiac_id))
            self._remplacer_caches(brainiac_id, etats)
        except BaseException:
            self._conn.rollback()
            raise
        self._conn.commit()
        return etats

    def _remplacer_caches(self, brainiac_id: str, etats: list[EtatConcept]) -> None:
        self._conn.execute("DELETE FROM fsrs WHERE brainiac_id = ?", (brainiac_id,))
        self._conn.execute("DELETE FROM maitrise WHERE brainiac_id = ?", (brainiac_id,))
        for e in etats:
            if e.brainiac_id != brainiac_id:
                raise ValueError(f"état de {e.brainiac_id} écrit pour {brainiac_id}")
            self._conn.execute(
                "INSERT INTO fsrs (brainiac_id, concept_id, carte_json) VALUES (?, ?, ?)",
                (e.brainiac_id, e.concept_id, e.carte_json),
            )
            self._conn.execute(
                "INSERT INTO maitrise (brainiac_id, concept_id, etat, acquis_le, nb_revues)"
                " VALUES (?, ?, ?, ?, ?)",
                (
                    e.brainiac_id,
                    e.concept_id,
                    e.etat,
                    None if e.acquis_le is None else vers_iso(e.acquis_le),
                    e.nb_revues,
                ),
            )

    def etat(self, brainiac_id: str) -> list[EtatConcept]:
        lignes = self._conn.execute(
            "SELECT f.concept_id, f.carte_json, m.nb_revues, m.acquis_le"
            " FROM fsrs f JOIN maitrise m"
            " ON m.brainiac_id = f.brainiac_id AND m.concept_id = f.concept_id"
            " WHERE f.brainiac_id = ? ORDER BY f.concept_id",
            (brainiac_id,),
        )
        return [
            EtatConcept(
                brainiac_id=brainiac_id,
                concept_id=concept_id,
                carte_json=carte_json,
                nb_revues=nb_revues,
                acquis_le=None if acquis_le is None else depuis_iso(acquis_le),
            )
            for concept_id, carte_json, nb_revues, acquis_le in lignes
        ]

    # --- sauvegarde (#3) ---

    def integre(self) -> bool:
        (resultat,) = self._conn.execute("PRAGMA integrity_check").fetchone()
        return bool(resultat == "ok")

    def copier_vers(self, destination: Path) -> None:
        """Copie cohérente même en WAL et pendant une écriture (jamais un `cp`)."""
        self._conn.execute("VACUUM INTO ?", (str(destination),))


def concepts_references_en_lecture(chemin: Path) -> set[str]:
    """Concepts cités par le journal, lus sans migrer ni verrouiller en écriture (publication)."""
    conn = sqlite3.connect(f"file:{chemin}?mode=ro", uri=True)
    try:
        return {cid for (cid,) in conn.execute("SELECT DISTINCT concept_id FROM revue")}
    finally:
        conn.close()


class IndexConcepts:
    """Recherche plein texte des concepts (FTS5), en mémoire et reconstruite depuis les
    fichiers de la bibliothèque : rien n'est stocké dans la base d'état (inv. 10)."""

    def __init__(self, entrees: Iterable[tuple[str, str, str, str]]) -> None:
        """`entrees` : (id, titre, domaine, texte) par concept."""
        self._conn = sqlite3.connect(EN_MEMOIRE)
        self._conn.execute(
            "CREATE VIRTUAL TABLE concept_fts USING fts5("
            "id UNINDEXED, titre, domaine UNINDEXED, texte,"
            " tokenize = 'unicode61 remove_diacritics 2')"
        )
        self._conn.executemany("INSERT INTO concept_fts VALUES (?, ?, ?, ?)", entrees)

    def __enter__(self) -> IndexConcepts:
        return self

    def __exit__(
        self,
        type_: type[BaseException] | None,
        valeur: BaseException | None,
        trace: TracebackType | None,
    ) -> None:
        self._conn.close()

    def chercher(self, mots: list[str], n: int) -> list[tuple[str, str, str]]:
        """Les `n` concepts les plus proches (id, titre, domaine), meilleur d'abord ; un mot du
        titre pèse dix fois un mot de la leçon.

        Chaque mot est cherché comme préfixe et entre guillemets : aucune syntaxe FTS5
        venue de l'appelant n'est interprétée."""
        propres = [m.replace('"', "") for m in mots if m.replace('"', "")]
        if not propres:
            return []
        requete = " OR ".join(f'"{m}"*' for m in propres)
        lignes = self._conn.execute(
            "SELECT id, titre, domaine FROM concept_fts WHERE concept_fts MATCH ?"
            " ORDER BY bm25(concept_fts, 0.0, 10.0, 0.0, 1.0), id LIMIT ?",
            (requete, n),
        )
        return [(i, t, d) for i, t, d in lignes]
