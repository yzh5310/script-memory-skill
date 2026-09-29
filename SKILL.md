---
name: script-memory
description: Normalise a theatre script, dialogue, or speech draft in any common file format and turn it into a single-file offline memorisation trainer, without altering one word of dialogue. Use it when a performer or speaker must memorise lines, a monologue, or a speech and wants role-aware rehearsal, a beat skeleton, anchor cues and a printable cue sheet. Covers script normalisation and rehearsal-tool generation; it does not translate, rewrite, score, or write scripts.
agent_created: true
---

# Script Memory

Turn a script into two deliverables: a normalised script document whose dialogue is
byte-identical to the original, and a single-file offline rehearsal page that the
performer actually studies from.

The page is not a script reader. It runs a specific memorisation order — skeleton
first, then anchors, then reusable parts, then a physical cue sheet — and every
control on the page exists to enforce one of those steps. Do not reorder or drop them.

## Non-negotiable rules

1. **Dialogue is frozen.** Never fix a typo, never "improve" grammar, never smooth a
   hesitation inside a `k=L` line — even when the typo is obvious. Flag it in the
   delivery notes instead.
2. **Only scaffolding may be normalised.** Section numbering, speaker-label form,
   and the markers used for stage directions are yours to unify. Nothing the actor
   speaks is.
3. **Prove it, do not claim it.** `scripts/check_fidelity.py` must exit zero before
   delivery. A page that passes visual inspection but fails the fidelity gate is not
   deliverable.
4. **Ship one self-contained file.** No CDN, no build step, no network, no install.
   It must open from a USB stick and work on a phone.
5. **Never invent the performer's experience.** Do not fabricate personal stories,
   motivations, or biographical colour anywhere in the materials.
6. **Cap the skeleton at 6-10 segments.** Fewer means it breaks under a single
   forgotten line; more means memorising the skeleton becomes the burden.

## Workflow

### 1. Extract

```bash
python scripts/extract_script.py "<script file>" -o <workdir>
```

Read `<name>.txt` for the content. Consult `<name>.blocks.json` when you need
formatting evidence: `"runs"` present means a mixed-format paragraph, which is the
usual home of inline stage directions and delivery tips.

Then count the lines and the speakers, and identify which markers the source uses to
separate dialogue from action, setting, and delivery notes. Those counts become the
regression baseline for the rest of the job.

Read [references/extraction.md](references/extraction.md) for per-format notes and
the order in which to investigate an empty or truncated extraction.

### 2. Normalise the script document

Read [references/normalization.md](references/normalization.md) before touching
anything. It defines the boundary between scaffolding and dialogue, the four marker
classes, and the three traps that recur across scripts.

Produce a normalised document (Word or Markdown) in which:

- dialogue text is untouched, verbatim;
- speaker labels use one consistent full-width colon form;
- stage directions are marked `【场景】/【动作】/【提示】`;
- heading levels use one numbering system throughout.

Attach a "suspect but unchanged" list of typos and anomalies. `validate_data.py`
derives most of it automatically — do not eyeball this.

### 3. Shape the data

Author `data.json` against
[schemas/script-data.schema.json](schemas/script-data.schema.json). The shape is a
list of scenes, each holding items in reading order, where `k` selects the kind:

| `k` | meaning | example |
|---|---|---|
| `B` | skeleton segment heading | `{"k":"B","text":"拍 3 · 指错路"}` |
| `S` | setting | `{"k":"S","text":"校园国际文化节。"}` |
| `A` | action / blocking | `{"k":"A","text":"偷瞄小抄，手指滑错行。"}` |
| `T` | delivery tip | `{"k":"T","text":"说完停 1 秒，等观众笑。"}` |
| `L` | a spoken line | `{"k":"L","role":"A","text":"…","zh":"…"}` |

Also fill in `title`, `subtitle`, `roles`, `ensemble`, and the memory-method fields
`keyParts` and `rescueLines`. Role labels, the skeleton list, and the progress-key
slug are all derived when omitted, so a quick job can supply only `title` and
`scenes`.

Bilingual glosses (`zh`) are meaning-level gists, not translations — no line-by-line
equivalence required, and no attempt to render the original word choice.

### 4. Build

```bash
python scripts/build_memory_html.py data.json -o index.html
```

Validation runs first; the build aborts on structural errors unless `--force` is
given. The build re-reads its own output and confirms the payload round-trips.

### 5. Verify, in this order

```bash
python scripts/validate_data.py data.json --html index.html
python scripts/check_fidelity.py --source "<original file>" --data data.json
node scripts/smoke_boot.js index.html
```

All three must pass. The smoke test boots the page in a stub DOM and asserts that
every region actually rendered — a page whose script throws mid-initialisation still
looks fine in a plain editor, which is exactly how broken pages get shipped.

When rebuilding an existing page, pass the previous build as a second argument to
`smoke_boot.js` to prove the dialogue did not drift:

```bash
node scripts/smoke_boot.js new.html old.html
```

### 6. Deliver

Hand over the normalised document, the HTML page, and a short notes block:

- structure counts (scenes / segments / lines / the performer's lines);
- the suspect-but-unchanged list;
- which role is pre-selected, and that selecting a different one is one click;
- how to open it (browser, phone, offline) and the keyboard shortcuts.

Present the HTML file so it opens in a preview panel.

## Reading the room

Two shapes, one pipeline. Detect which one you have and let the page adapt — do not
fork the template.

**Dialogue (2+ speakers).** Roles are real, take-turns practice is the point. Keep
the partner panel. Set `ensemble` for unison lines. Assign a different voice per
role so the ear can tell who is speaking.

**Monologue (1 speaker).** A speech or solo. There is no partner, so pass a single
role (for example `"Speaker"`), leave `ensemble` empty, and set `beatUnit` to `段`.
The page hides the partner panel and the "skip to partner" controls automatically.
Role labels in the source document are scaffolding — normalise them; the speech text
itself is not.

## Quality bar

Before calling the job done, confirm:

- every `k=L` string survives `check_fidelity.py` byte-for-byte;
- the skeleton has 6-10 segments and each reads as a picture, not a summary;
- `keyParts` and `rescueLines` are filled with material actually present in the
  script, not generic advice;
- the page boots clean under `smoke_boot.js` with no `FAIL` lines;
- the suspect list is delivered rather than silently applied;
- the page opens offline with no console errors and no network requests.

## Bundled resources

| Path | Use |
|---|---|
| `template.html` | The page. `build_memory_html.py` injects data into it; adapt the data, not the template |
| `schemas/script-data.schema.json` | Normative shape of `data.json` |
| `references/extraction.md` | Per-format extraction, dependency fallbacks, triage order |
| `references/normalization.md` | What to unify, what to freeze, the recurring traps |
| `references/memory-methods.md` | Why each page region exists and how to tune it |
| `examples/mini-dialogue.data.json` | Two-speaker example |
| `examples/mini-monologue.data.json` | Single-speaker example |
| `scripts/extract_script.py` | Any format to text |
| `scripts/build_memory_html.py` | Data to page, with round-trip verification |
| `scripts/validate_data.py` | Structure check plus automatic anomaly list |
| `scripts/check_fidelity.py` | Release gate: dialogue unchanged |
| `scripts/smoke_boot.js` | Headless boot and regression test |
