# Security policy

## Supported versions

Freinet is alpha software. Only the latest commit on `main` receives fixes.

## Reporting a vulnerability

Please **do not open a public issue** for a security problem. Use GitHub's private vulnerability reporting (the "Report a vulnerability" button under the repository's Security tab), or write to dissatm@gmail.com with "Freinet security" in the subject.

Include what you found, how to reproduce it, and its impact. You should receive an acknowledgement within 7 days. Please give a reasonable delay before any public disclosure.

## Scope and threat model

Freinet runs on a personal computer and serves pages on a private network. The parts most worth reviewing:

- **QR feedback page** (`freinet/serveur.py`, `freinet/retour.py`, `freinet/espace.py`): private-address clients only, `Host` restriction, same-origin checks on POST, bounded bodies and timeouts, per-client connection and short-code attempt limits, strict headers. Known and accepted for V0: an attacker on the same local network with many addresses can exhaust the connection slots.
- **Access tokens** (`freinet/acces.py`): 128-bit random tokens and short codes, stored only as HMACs with a local key in `data/.cle-acces`.
- **Optional local JSON API** (`freinet/api_adviza.py`): off unless configured, bound to `127.0.0.1`, bearer tokens stored as SHA-256 fingerprints, idempotent actions with bounded JSON bodies.
- **Content pipeline**: web sources read during the fan-out are treated as hostile; published text is checked to be plain text without links or markup.

## Private data

Learner state (`data/`, `brainiacs/<learner>/`, generated plans and tickets) is git-ignored by design and must never be committed. If you find personal data in the repository, please report it privately as above.
