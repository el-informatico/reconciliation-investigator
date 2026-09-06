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
