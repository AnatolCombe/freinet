# Vision: the Freinet Box, a solar, offline cyberdeck for schools

> **Status: vision, planned.** Nothing in this document has been built, piloted or tested. There is no hardware prototype, no partner and no user beyond the author's own use of Freinet. Figures are given with their confidence level.

## Why Freinet fits offline schools

Freinet was designed for one learner at home, but its constraints are those of a school without grid power or internet:

| Freinet today | What it would mean offline |
|---|---|
| The ticket prints without any LLM (invariant 7) | lessons keep coming when the model, the network or the power budget is down |
| One SQLite file and Markdown content | no server, no cloud account, easy to copy and back up |
| The QR page serves private network addresses only | a local Wi-Fi access point is enough |
| Paper is the learner's interface | pupils do not need a phone or a screen |
| Content is validated before publication, by a human gate | a teacher stays in control of what reaches pupils |
| Spaced repetition decides what each learner revisits | each pupil gets an individual review sheet |

## The Freinet Box

```text
  ┌──────────────┐    ┌─────────┐    ┌───────────────────────────────┐
  │ solar panel  │───►│ battery │───►│ low-power computer (10-25 W)  │
  │ 100-200 Wp   │    └─────────┘    │ Freinet + small local model   │
  │ (estimate)   │                   └──────┬───────────────┬────────┘
  └──────────────┘                          │               │
                                   local Wi-Fi (no      thermal ticket
                                   internet)            printer
                                            │               │
                                            │        individual review
                                            │        tickets with QR codes
                                            │               │
                                            └──── ratings ◄─┘
                                            (QR page on the local Wi-Fi)
```

- **Paper for pupils without phones.** A thermal ticket printer produces individual review sheets every day. The spaced-repetition engine picks what each pupil should revisit. This is how Freinet already works for a single learner.
- **An assistant for the teacher, not the pupil.** A small local language model helps the teacher prepare a lesson, an exercise or a test. The teacher always approves before use, as the human gates of the fan-out pipeline do today.
- **Knowledge that grows and stays local.** Every item a teacher validates joins a shared library. Boxes exchange it by USB stick.
- **Guaranteed fallback.** If the model fails, the resources and printed sheets still work.

## Indicative hardware

| Need | Candidate | Confidence |
|---|---|---|
| Computer for a 1-3 billion parameter model | Raspberry Pi 5 (8 GB), about 7-10 W | third-party tests |
| Computer for a ~7 billion parameter model | Jetson Orin Nano Super, 25 W | third-party tests |
| Solar autonomy for a day of use | 100-200 Wp kit with battery | estimate |
| Thermal ticket printer | Epson TM-m30 range | used by this project today |

## What would have to change in Freinet

These are open engineering questions, not features:

- **Many pupils per box.** The schema already carries `brainiac_id` on every state table; selection, rendering and the QR page work per learner. Printing for a whole class, and rating without a phone per pupil (for example a teacher entering ratings, or a shared device), are not designed yet.
- **Linux scheduling.** Scheduling and alerts are macOS launchd today; a single-board computer needs systemd timers or cron.
- **Local models.** The fan-out runs LLM agents in Claude Code today. A local, smaller model behind the same human gates is not implemented.
- **Library exchange.** Publication is already atomic and validated; merging libraries from several boxes (USB) is not designed yet.
- **Languages and curricula.** Learner-facing output exists in French and English. Other languages, and maps aligned with a national curriculum, would be content work done with teachers.
- **Protection of minors' data.** Learner state stays local and private by design (invariant 11); a deployment would still need an explicit data-protection policy.

## Context

Offline schools and learning centres, including in displacement settings, are the intended context. Any pilot would be designed with local education actors; none exists today.
