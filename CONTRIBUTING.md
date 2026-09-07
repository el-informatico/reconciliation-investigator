# Contributing to reconciliation-investigator

## Commit messages and code comments: no AI-tool attribution

Commit messages, code comments, and docstrings in this repository must
never carry AI-tool attribution or authorship references:

- No `Co-Authored-By:` trailers naming an AI tool or vendor (Claude,
  Claude Code, Anthropic, ChatGPT, OpenAI, Copilot, ...).
- No "Generated with ...", "Written by ...", "Assisted by ..." credit
  lines for AI tools, and no robot-emoji signatures.
- No prose in a comment or docstring claiming an AI tool authored the
  code it sits in.

Mentioning an AI tool as **subject matter** is fine and sometimes
required — e.g. the credential policy that reserves the Z.AI key for
Claude Code, provider-migration subjects like "remove the Anthropic
path", or dated audit reports analyzing agent behavior. The rule bans
authorship claims, not words.

**Why:** the commit history was deliberately rewritten (2026-09-05,
stage 2) to remove such trailers, and the author of record is the
human owner. The convention regressed once (a local-only commit,
2026-09-06) with nothing firing, so it is now enforced mechanically:
`scripts/hooks/commit-msg` fails any commit whose message matches an
attribution pattern. It is wired through the same
`git config core.hooksPath scripts/hooks` mechanism as the pre-commit
segregation guard and is bypassable only the same ways (`--no-verify`
— don't).

## Sensitive content: raw strings never enter new history

Commit messages, staged additions, and documents in the repository
tree must not introduce raw sensitive content: local filesystem paths
(user-home and Windows-mount paths), sibling-project identifiers, or
hostnames.

- Planning/audit documents that must quote such strings by structural
  necessity are written OUTSIDE the repository working tree from the
  moment they are created — never inside the repo, even temporarily,
  even untracked (one `git add -A` away from history). On 2026-09-06
  the three planning documents of the privacy-audit effort were
  relocated accordingly; see
  docs/SENSITIVE-PLANNING-DOCS-RELOCATED.md.
- Completion summaries, commit messages, and review replies use
  tokenized/category references ("sibling-project names", "home
  paths"), never the raw strings.
- The filename classes `*privacy-audit-*.md`,
  `*rewrite-execution-plan-*.md`, `*backup-chain-investigation-*.md`
  (prefix-optional, so both `agent-memory-privacy-audit-…` and the
  unprefixed `backup-chain-investigation-…` real-name shapes match)
  under `docs/` and `agent-memory/` are gitignored as a safety net; a
  deliberately tokenized document of one of those classes that must be
  tracked needs `git add -f`.

**Why:** this repository is intended for a public flip. Raw strings of
these classes already exist in frozen tracked evidence under the
annotate-don't-erase rule (D-2026-09-05-01), and a scoped history
rewrite addresses those separately — this rule's job is that no NEW
occurrence enters history.

**Mechanical gate:** `scripts/guard-sensitive-content.sh` (invoked by
`scripts/hooks/pre-commit`) fails a commit whose staged ADDED lines
contain any token from a locally configured list, and
`scripts/hooks/commit-msg` applies the same list to the commit
message. The list lives at `<git-dir>/sensitive-tokens` — literal
fixed strings, one per line, never tracked (a reference copy is kept
outside the repository beside the relocated planning documents; reseed
with a plain copy after a fresh clone). Absent or empty list = check
disabled (fail-open); present but not a readable regular file (chmod
000, a directory at the path, a dangling symlink) = commit refused
(fail closed), in both the pre-commit guard and commit-msg. Bypassable
only the same ways as the other hooks
(`--no-verify` — don't).

## Commit style

Match the established history: short descriptive subject (~50-72
characters), a body only when the "why" needs one line. Author
identity comes from the repo-local git config
(`juanz <204210901+el-informatico@users.noreply.github.com>`);
never fabricate a different author.

## Verification

`scripts/verify.sh` is the authoritative end-to-end evidence. Step 6
is a LIVE benchmark — run it only when a benchmark is explicitly
intended. The offline suite is `uv run --locked pytest -q`.
