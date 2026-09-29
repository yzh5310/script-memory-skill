# CLAUDE.md

See `SKILL.md` for the workflow and `AGENTS.md` for the hard constraints.

The one rule that matters most: dialogue in a `k=L` line is frozen. Do not fix
typos, do not smooth grammar, do not touch spacing. Run
`python scripts/check_fidelity.py --source "<original>" --data data.json` and
require exit code `0` before delivering anything.
