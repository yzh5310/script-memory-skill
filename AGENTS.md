# script-memory — agent rules

Read `SKILL.md` first. It is the normative workflow; this file is the hard-constraint
summary that must hold on any platform.

## Never

- Never edit, fix, or "improve" text inside a `k=L` line — not a typo, not grammar,
  not spacing. Report it instead.
- Never normalise anything the performer speaks. Only scaffolding is yours:
  numbering, speaker labels, and stage-direction markers.
- Never deliver without all three gates exiting clean, and `check_fidelity.py`
  exiting `0`.
- Never add a network request, CDN link, install step, or build step to the page.
- Never fabricate personal stories, motivations, or biographical detail.
- Never let the skeleton exceed 10 segments.

## Always

1. `python scripts/extract_script.py "<source>" -o <workdir>` — then record the line
   and speaker counts. They are the regression baseline for the rest of the job.
2. Author `data.json` against `schemas/script-data.schema.json`.
3. Cap the skeleton at 6-10 segments, each read as a picture, not a summary.
4. Run, in this order:
   ```bash
   python scripts/validate_data.py  data.json --html index.html
   python scripts/check_fidelity.py --source "<original file>" --data data.json
   node   scripts/smoke_boot.js     index.html
   ```
5. Deliver the page, the structure counts, and the "suspect but unchanged" list.

## Shape detection

| Script | Roles | `ensemble` | `beatUnit` |
|---|---|---|---|
| Dialogue (2+ speakers) | one per speaker, plus the unison label | the unison label | `拍` |
| Monologue / speech | a single role, e.g. `Speaker` | `""` | `段` |

The page adapts by itself. Do not fork the template.

## Files

`template.html` is data-driven. Change `data.json` for content; touch `template.html`
only for interaction or styling, and re-run `smoke_boot.js` afterwards.
