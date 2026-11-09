-- 002 — le plan du jour garde la notion nouvelle présentée : la sélection ne la repropose
-- plus et la fait réviser dès le lendemain, même sans aucune revue (sinon boucle).
ALTER TABLE plan_du_jour ADD COLUMN nouvelle TEXT;
