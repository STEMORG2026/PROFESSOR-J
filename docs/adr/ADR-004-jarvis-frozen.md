# ADR-004: Freeze JARVIS — PROFESSOR-J is the Sole Successor

- **Status**: accepted
- **Date**: 2026-08-25
- **Version**: 0.0.1
- **Decider**: Sajan (Principal Architect)

## Context

ADR-001 (2026-08-21) adopted PROFESSOR-J as the successor to JARVIS and
recorded that "JARVIS remains an independent, maintained peer." In practice, the
owner has now decided to **freeze JARVIS entirely**: no further development,
writes, commits, or pushes to the JARVIS repository. JARVIS is retained only as a
read-only reference/history; PROFESSOR-J is the sole successor and the only
active platform going forward.

This makes the ownership model unambiguous:

- **JARVIS (`Er-Sajan-PLG/JARVIS`)**: frozen, read-only. Read/search permitted;
  no writes by anyone (including agents).
- **PROFESSOR-J (`Er-Sajan-PLG/PROFESSOR-J`)**: the active successor. All new
  platform work lands here.

## Decision

1. **JARVIS is frozen (read-only).** No new commits, branches, pushes, or
   merges to `Er-Sajan-PLG/JARVIS`. No agent or tooling may write to it.
   Access is read/search only, for reference and history.
2. **PROFESSOR-J is the sole successor and active development target.** Any
   capability, fix, or feature that would previously have gone to JARVIS now
   belongs in PROFESSOR-J.
3. **Supersedes ADR-001's "JARVIS remains an independent, maintained peer"**
   consequence. JARVIS is retained but no longer maintained/updated.
4. Pattern-level inheritance from JARVIS into PROFESSOR-J continues to be
   recorded in ADRs (see ADR-002).

## Consequences

### Positive
- Single, unambiguous source of truth for active platform work (PROFESSOR-J).
- Clear read-only boundary prevents accidental writes to the legacy codebase.
- JARVIS history and patterns remain inspectable for porting.

### Negative
- No further maintenance to JARVIS; any latent JARVIS-only bug is not fixed.
- Future work must port (pattern-level) any needed JARVIS capability rather than
  editing JARVIS directly.

### Neutral
- JARVIS becomes a static reference archive.
- The `webapp`/task branches in JARVIS remain frozen in place (read-only).

## Alternatives

### Alternative 1: Keep JARVIS as an actively-maintained peer
Rejected — the owner explicitly wants JARVIS frozen to avoid split ownership and
any risk of writing to the legacy/copyright-exposed name.

### Alternative 2: Delete/archive JARVIS entirely
Rejected — the capability surface and patterns remain worth retaining as a
read-only reference for pattern-level porting.

## Related
- Supersedes the "JARVIS remains an independent, maintained peer" consequence in
  ADR-001.
- ADR-002 (pattern-level inheritance from JARVIS) remains in force.
- PROFESSOR-J `docs/GOVERNANCE.md`.
