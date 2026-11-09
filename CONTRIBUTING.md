# Contributing to Freinet

Thank you for your interest. Freinet is a small project with strict rules, because it is about learners' progress and their private data. This guide explains how to work on it.

## Set up

```bash
git clone https://github.com/AnatolCombe/freinet.git && cd freinet
uv sync
uv run pytest
```

Python 3.11 or newer. Dependencies are pinned in `pyproject.toml` and locked in `uv.lock`.

## Before you open a pull request

All four must pass, with zero warnings:

```bash
uv run pytest                    # coverage must stay ≥ 85 %
uv run ruff check .
uv run ruff format --check .
uv run mypy --strict
```

The end-to-end check runs all of them plus the V0 scenario:

```bash
scripts/verif-v0.sh
```

## Project rules

- **One file, one responsibility, at most 400 lines.** Split rather than grow.
- **Only `freinet/base/` talks to SQLite.** No other module imports `sqlite3` or runs SQL (a test enforces it).
- **The review log only grows.** A correction is a new row, never an UPDATE.
- **No LLM decides mastery or scheduling**, and the ticket must print without an LLM. Any LLM call needs a deterministic fallback.
- **No threshold hard-coded.** Constants live in `_config/` and are read by the code.
- **Nothing generated at print time.** Content reaches a ticket only through `06_publication`.
- **No personal data in the repository.** Learner folders, the database, plans and tickets are git-ignored; keep it that way. Use fictional learners in tests.
- **Generated files are never edited by hand**: run `scripts/regen-index.py` after changing `bibliotheque/`.
- **Rendering references**: if you change the ticket on purpose, run `uv run pytest --update-ref`, then look at the regenerated PNGs in `tests/ticket/reference/` before committing them.
- **Stage contracts**: a new pipeline stage needs a `CONTEXT.md` with Inputs, Process, Outputs and one Human check (`scripts/verif-contrats.py`).

## Language

Code identifiers, comments and internal stage contracts are in French. Public documentation is in English. New code may keep the surrounding French vocabulary for consistency; English comments are welcome. Learner-facing strings must exist in both French and English (`freinet/langue.py`, `freinet/libelles_espace.py`).

## Commits and pull requests

- Small, focused pull requests; one concern each.
- Commit messages: `type(scope): summary` (for example `fix(rendu): wrap long Hebrew words`).
- Describe what changed, why, and how you tested it. Link the issue.
- Do not refactor unrelated code in the same pull request.

## Content contributions

Concept maps are welcome as proposals. Every anecdote and fact needs a source from the trusted-source registry (`_config/sources/`). Finance content is educational only and must carry the disclaimer. Content must pass the publication validator: put your files in the fan-out `output/` folders and run `uv run python -m freinet.publication --verifier`.

## Where to start

See [docs/good-first-issues.md](docs/good-first-issues.md) and [docs/architecture.md](docs/architecture.md).

By participating, you agree to follow the [Code of Conduct](CODE_OF_CONDUCT.md).
