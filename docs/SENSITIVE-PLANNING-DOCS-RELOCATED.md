# Sensitive planning documents relocated outside this repository

On 2026-09-06 the following documents were moved OUT of this
repository's working tree to a local-only directory on the same
machine, outside the repository (the path is deliberately not written
here; it is recorded in the operator's local notes and in the
MANIFEST inside that directory):

1. `docs/agent-memory-privacy-audit-2026-09-06.md`
2. `docs/agent-memory-rewrite-execution-plan-2026-09-06.md`
3. `docs/backup-chain-investigation-2026-09-06.md`

## What they were, and why they had to leave

These are the planning documents of the 2026-09-06 privacy-audit
effort. By structural necessity they quote the raw sensitive strings
they plan to redact — sibling-project names, local filesystem paths,
Windows-mount paths. Keeping them inside the repository directory,
even as untracked files, left them one accidental `git add -A` away
from being committed, and relied on every future session remembering
"this one is untracked". They were therefore relocated physically, not
gitignored-in-place. None of the three was ever tracked (verified
against HEAD and the full history tree at relocation time), so no
history rewrite is needed on their account.

## The work they describe is NOT lost and NOT executed

The privacy audit findings, the agent-memory history-rewrite execution
plan (commands, hash mappings, diff content), and the backup-chain
investigation all remain fully intact in the relocated copies —
content integrity was verified by sha256 digests taken before and
after the move. The redaction/rewrite itself remains a separate,
already-scoped follow-up task and has NOT been executed as of this
marker.

## Safeguards added with the relocation

- `.gitignore` patterns for these filename classes under `docs/` and
  `agent-memory/` (safety net only — see that file for the exact
  patterns and the `git add -f` escape hatch).
- `scripts/guard-sensitive-content.sh`, invoked by
  `scripts/hooks/pre-commit`, refuses a commit whose staged added
  lines contain configured sensitive tokens; `scripts/hooks/commit-msg`
  applies the same list to the commit message. The token list lives at
  `<git-dir>/sensitive-tokens` — never in tracked content; a reference
  copy sits beside the relocated documents.

## Hard rule for future sessions

Any task whose output must quote raw sensitive content (local
filesystem paths, sibling-project identifiers, hostnames, credentials)
for planning or audit purposes MUST (a) write the full-detail file
OUTSIDE the repository's working tree from the start — never create it
inside the repo, even temporarily, even intending to move it later —
and (b) use tokenized/category references in every completion summary
and reply, never the raw strings. Canonical rule and rationale:
CONTRIBUTING.md.
