# PROFESSOR-J — Development Skills (`agents_dev/skills`)

Skills PROFESSOR-J loads (or a human/agent reads) to perform **repeated development work**
across the ecosystem. Each is a capability definition with a `data:` block mirroring the
`SkillMetadata` schema in `app/skills/base.py` (`name`, `description`, `version`, `author`,
`category`, `tags`, `requires_approval`, `timeout_seconds`), plus the reusable procedure,
verification, and references. These are **mechanism/knowledge inputs**, never authority —
repository governance always wins (see `../AGENTS.md` §2).

## Adding a skill

1. Drop a markdown file here following the `data:`-block + `When to use` / `Procedure` /
   `Verification` / `References` shape.
2. Keep `requires_approval: true` for anything that commits/merges/deploys or mutates a
   peer repository.
3. Reference the authoritative process so the skill stays thin and the source of truth stays
   in one place (drift audits: source wins).
4. Register it with the runtime registry if engine-loading is required (not just agent-read).

## Cross-repo working folder

Skills that operate on a **specific peer repo** should link to the dedicated working folder
under `agents_dev/<repo>/` (e.g. `agents_dev/stem-tuition/`) which holds `current-state.md`
and `workflow.md` for that seam. Keep `current-state.md` refreshed after each batch so
PROFESSOR-J always "knows what's going on."
