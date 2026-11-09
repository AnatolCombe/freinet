-- 001 — schéma initial. SQL standard (Postgres le jour de l'hébergement, #55).
-- Identifiants : UUID en TEXT. Horodatages : ISO 8601 UTC en TEXT.
-- Toute table d'état porte brainiac_id (inv. 10). `revue` est en ajout seul (inv. 3).

CREATE TABLE brainiac (
    brainiac_id        TEXT PRIMARY KEY,
    nom                TEXT NOT NULL UNIQUE,
    fuseau             TEXT NOT NULL,
    canal              TEXT NOT NULL DEFAULT 'thermique',
    dosage_projets     INTEGER NOT NULL DEFAULT 60,
    dosage_declares    INTEGER NOT NULL DEFAULT 25,
    dosage_serendipite INTEGER NOT NULL DEFAULT 15,
    cree_le            TEXT NOT NULL,
    CHECK (dosage_projets + dosage_declares + dosage_serendipite = 100)
);

CREATE TABLE inscription (
    brainiac_id  TEXT NOT NULL REFERENCES brainiac (brainiac_id),
    carte_id     TEXT NOT NULL,
    quete_active TEXT,
    inscrit_le   TEXT NOT NULL,
    PRIMARY KEY (brainiac_id, carte_id)
);

CREATE TABLE plan_du_jour (
    plan_id      TEXT PRIMARY KEY,
    brainiac_id  TEXT NOT NULL REFERENCES brainiac (brainiac_id),
    date_logique TEXT NOT NULL,
    jeton_hache  TEXT UNIQUE,
    statut       TEXT NOT NULL CHECK (statut IN ('planifie', 'imprime', 'note')),
    cree_le      TEXT NOT NULL,
    UNIQUE (brainiac_id, date_logique),
    UNIQUE (brainiac_id, plan_id)
);

CREATE TABLE revue (
    revue_id    TEXT PRIMARY KEY,
    brainiac_id TEXT NOT NULL REFERENCES brainiac (brainiac_id),
    concept_id  TEXT NOT NULL,
    question_id TEXT NOT NULL,
    nature      TEXT NOT NULL CHECK (nature IN
                  ('rappel', 'application', 'transfert', 'piege', 'amorce_feynman', 'pre_test')),
    note        INTEGER NOT NULL CHECK (note BETWEEN 1 AND 4),
    repondu_le  TEXT NOT NULL,
    saisi_le    TEXT NOT NULL,
    canal       TEXT NOT NULL,
    plan_id     TEXT,
    corrige_id  TEXT,
    UNIQUE (brainiac_id, revue_id),
    -- clés composites : un plan ou une correction ne traverse jamais d'un élève à l'autre
    FOREIGN KEY (brainiac_id, plan_id) REFERENCES plan_du_jour (brainiac_id, plan_id),
    FOREIGN KEY (brainiac_id, corrige_id) REFERENCES revue (brainiac_id, revue_id)
);

CREATE INDEX revue_par_brainiac ON revue (brainiac_id, repondu_le, revue_id);

-- RAISE(ABORT) est propre à SQLite : la migration Postgres réécrira ces triggers en PL/pgSQL.
CREATE TRIGGER revue_sans_update BEFORE UPDATE ON revue
BEGIN
    SELECT RAISE(ABORT, 'revue est en ajout seul (inv. 3)');
END;

CREATE TRIGGER revue_sans_delete BEFORE DELETE ON revue
BEGIN
    SELECT RAISE(ABORT, 'revue est en ajout seul (inv. 3)');
END;

-- INSERT OR REPLACE supprime la ligne en conflit sans déclencher revue_sans_delete :
-- on refuse donc toute insertion qui réutiliserait un revue_id existant.
CREATE TRIGGER revue_sans_remplacement BEFORE INSERT ON revue
WHEN EXISTS (SELECT 1 FROM revue WHERE revue_id = NEW.revue_id)
BEGIN
    SELECT RAISE(ABORT, 'revue est en ajout seul (inv. 3)');
END;

-- Caches recalculables par rejeu de `revue` (inv. 4). FSRS suit le concept (A8).
CREATE TABLE fsrs (
    brainiac_id TEXT NOT NULL REFERENCES brainiac (brainiac_id),
    concept_id  TEXT NOT NULL,
    carte_json  TEXT NOT NULL,
    PRIMARY KEY (brainiac_id, concept_id)
);

CREATE TABLE maitrise (
    brainiac_id TEXT NOT NULL REFERENCES brainiac (brainiac_id),
    concept_id  TEXT NOT NULL,
    etat        TEXT NOT NULL CHECK (etat IN ('en_cours', 'acquis')),
    acquis_le   TEXT,
    nb_revues   INTEGER NOT NULL,
    PRIMARY KEY (brainiac_id, concept_id)
);
