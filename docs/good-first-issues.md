# Good first issues

Five issues ready to be opened on GitHub. Each has a title and a body; labels suggested in brackets.

---

## 1. Document the `_config/` files in English

**Labels:** `good first issue`, `documentation`

**Body:**

The files in `_config/` are read by the code and define how Freinet behaves: mastery constants (`regle-acquis.md`), daily dose (`dose.md`), printer (`imprimante.md`), QR page (`retour.md`), trusted sources (`sources/`), general-section lists (`general/`). They are documented in French only.

Add `docs/configuration.md` that explains, in English, each file, each key, its default value and which module reads it (`freinet/constantes.py`, `dose.py`, `imprimante.py`, `acces.py`, `sources.py`, `general.py`). Do not change the files themselves: the parsers expect their current French keys.

**Done when:** every key of every `_config/*.md` file is described, and the README links to the new page.

---

## 2. Provide a Linux scheduling recipe (systemd timer or cron)

**Labels:** `good first issue`, `enhancement`, `linux`

**Body:**

The morning job (`python -m freinet.matin`, 05:57), the heartbeat (`python -m freinet.heartbeat`, 07:00) and the QR page server (`python -m freinet.serveur`) are installed as macOS launchd agents by `freinet/launchd.py`. There is no equivalent for Linux, which matters for a single-board computer.

Write `docs/linux.md` with systemd user units and timers (or a crontab) that run the same three commands from the repository's `.venv`, with the same environment variables. `matin` and `heartbeat` already serialise themselves through a file lock (`freinet/verrou.py`), so re-runs are safe. Note that `heartbeat` currently sends macOS notifications.

**Done when:** the recipe is tested on a Linux machine and the steps are reproducible from a fresh clone.

---

## 3. Publish an English overlay for the demo map

**Labels:** `good first issue`, `content`, `i18n`

**Body:**

English-speaking learners read `bibliotheque/en/`, an overlay with the same ids as the French library. The demo map `harmonie-demo` in `bibliotheque/` has no English overlay in the repository, so an English demo learner gets English labels with French content.

Translate the four concepts, their questions, the quest and the map title into `bibliotheque/en/`, following the structure produced by `fanout/07_traduction` and the test helper `surcouche_en` in `tests/bibliotheque/demo.py`. Then run `scripts/regen-index.py` and the test suite.

**Done when:** a learner with `langue: "en"` in `_config/general/general.md` gets a fully English ticket from the demo map, and `uv run pytest` passes.

---

## 4. Translate the open course pages for English-speaking learners

**Labels:** `good first issue`, `i18n`

**Body:**

Inside a ticket's space (`/r/<token>/…`), pages follow the learner's language. The open pages served without a token (`/cours`, `/cours/<map>`, `/fiche/<concept>`, `/c`) are always in French (see `quotidien/04_retour/CONTEXT.md`).

Add an English variant of these pages, for example selected by a `?lang=en` query parameter or an `/en/` prefix, reusing the labels in `freinet/libelles_espace.py` and the English library overlay. Keep the existing security checks of `freinet/serveur.py` unchanged.

**Done when:** the open pages render in English on request, with tests in `tests/retour/`, and French remains the default.

---

## 5. Start restart tickets on a Monday or the first of the month

**Labels:** `good first issue`, `enhancement`, `engine`

**Body:**

After at least 3 days without feedback while work was waiting, the selection prints a gentle restart ticket (thread of the quest, easy questions, no new concept). `_config/dose.md` notes a planned refinement that is not applied yet: prefer starting the restart on a Monday or the first day of a month ("fresh start" effect).

Design and implement this in `freinet/selection.py` without breaking reproducibility (same seed and state must give the same plan, invariant 6). Any new constant goes into `_config/dose.md` and is read by `freinet/dose.py`, never hard-coded.

**Done when:** behaviour is covered by tests in `tests/selection/`, the rule is documented in `_config/dose.md`, and coverage stays at or above 85 %.
