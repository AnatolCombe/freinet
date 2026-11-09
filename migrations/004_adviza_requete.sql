-- 004 — API ADVIZA (PROF-A3) : les requêtes d'action déjà traitées, par clé d'idempotence.
-- Ajout seul, comme `revue` (inv. 3) : une réponse enregistrée ne change jamais ; la même clé
-- rend la même réponse. `brainiac_id` partout (inv. 10) : la clé d'un élève ne rencontre
-- jamais celle d'un autre. Ce n'est pas un état : rien ne s'y recalcule (inv. 4).
CREATE TABLE adviza_requete (
    brainiac_id TEXT NOT NULL REFERENCES brainiac (brainiac_id),
    cle         TEXT NOT NULL,
    action      TEXT NOT NULL,
    empreinte   TEXT NOT NULL,
    reponse     TEXT NOT NULL,
    recue_le    TEXT NOT NULL,
    PRIMARY KEY (brainiac_id, cle)
);

-- RAISE(ABORT) est propre à SQLite : la migration Postgres réécrira ces triggers en PL/pgSQL.
CREATE TRIGGER adviza_requete_sans_update BEFORE UPDATE ON adviza_requete
BEGIN
    SELECT RAISE(ABORT, 'adviza_requete est en ajout seul');
END;

CREATE TRIGGER adviza_requete_sans_delete BEFORE DELETE ON adviza_requete
BEGIN
    SELECT RAISE(ABORT, 'adviza_requete est en ajout seul');
END;

-- INSERT OR REPLACE supprimerait la ligne en conflit sans déclencher le trigger de DELETE.
CREATE TRIGGER adviza_requete_sans_remplacement BEFORE INSERT ON adviza_requete
WHEN EXISTS (SELECT 1 FROM adviza_requete WHERE brainiac_id = NEW.brainiac_id AND cle = NEW.cle)
BEGIN
    SELECT RAISE(ABORT, 'adviza_requete est en ajout seul');
END;
