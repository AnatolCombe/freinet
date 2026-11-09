-- 003 — retour du QR (PROF-6) : le code court de secours (#34) est haché comme le jeton (A1),
-- et le joker « je sais déjà » (#26) porte sur la notion nouvelle du jour.
ALTER TABLE plan_du_jour ADD COLUMN code_hache TEXT;
ALTER TABLE plan_du_jour ADD COLUMN joker INTEGER NOT NULL DEFAULT 0 CHECK (joker IN (0, 1));
CREATE UNIQUE INDEX plan_du_jour_code ON plan_du_jour (code_hache);
