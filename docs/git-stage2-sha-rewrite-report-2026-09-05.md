# Stage 2 SHA-rewrite report (2026-09-05)
> AMENDED 2026-09-07: this report references the agent-memory/ directory, which was removed from repository history by the 2026-09-07 excision rewrite; those artifacts are retained only in the author's private local archive, never in this repository.

**Status: REWRITE COMPLETE AND VERIFIED — 19 commits preserved in order; ranks
1–18 trees byte-identical to the originals; rank 19 is the single fold commit
(+LICENSE, README MIT→Apache line, 3 SHA remaps); all identities normalized;
zero unexplained stale commit-SHA references (category E = 0).**
Classification tags: MEASURED / OBSERVED / DOCUMENTED / CALCULATED / PROJECTED / UNKNOWN.

## 1. Old → new commit map (19 entries, oldest first) (MEASURED)

| # | Old (full) | New (full) | Old short | New short |
|---|---|---|---|---|
| 1 | daedc780953416fe2a13b22fd4795256601dc2ba | 7144e90ce6a7e00581cf7f09d85e73a58c739bb5 | daedc78 | 7144e90 |
| 2 | 88303b7341e909f680d2c0c82f0581e09d8627cc | f067bcd5ae82bfb4e4f499491684700f8a9ff259 [CORRECTED 2026-09-07 — commit pruned by the agent-memory excision rewrite; see the operative execution plan's §2.4 commit map] | 88303b7 | f067bcd |
| 3 | abac42a9966df331f717ffa987e421b2d65e027a | 811df147541eb8b97e1d510ec125d7b6841e0ca9 | abac42a | 811df14 |
| 4 | df44a8c4b8c4816d6ec2f2d6d63faa7c6c4854f8 | 2fbfab950bc40f4a5c9c6128a09d70e7d7330e31 | df44a8c | 2fbfab9 |
| 5 | ceed30c364ee71e4f241bd430312bed6a16352ae | b1531548c1d895be0d797b00dee10df6f7a44496 | ceed30c | b153154 |
| 6 | 8bc8331746b2e82546767f4ce0cd568bd5205af4 | 68d505f5672dd44ea65dda635058783cc5218b8a | 8bc8331 | 68d505f |
| 7 | c1e0b0b8d18b173d6724104151cc2a81286acca0 | dc9f797f3e39effceb364d22c1f6640457d0ee42 | c1e0b0b | dc9f797 |
| 8 | b5e5df0a7329d10442511a83cb997815379bf771 | 402e2cfd43a00f192763c46289e9de468e6f90cd | b5e5df0 | 402e2cf |
| 9 | 3e194f17cb2c2734570ec3252343e5e8f5efbda2 | ddf1f424a99f52b567975db89ff8086153785884 | 3e194f1 | ddf1f42 |
| 10 | 68aebd3757447fec3327c712eec33fdf3142884d | 714a2828d5f27345355c6b45d0f3311d7b95b761 | 68aebd3 | 714a282 |
| 11 | 2ef1a5100dbedcccf91493a6aba8397b0491960d | cf58ddfb90029d3d50ab11785831f49143feb392 | 2ef1a51 | cf58ddf |
| 12 | 6b8e29fe69a5fb3561b6d8be6b00861d84e6f771 | f00d6247c37cc8e3e22a77f5f6c0d45264009306 | 6b8e29f | f00d624 |
| 13 | c2803a550fb686108e5bc83f4a74b727520fdc59 | af90ddc72f865269d5c83c49ac8be81df115b9e1 | c2803a5 | af90ddc |
| 14 | 48a45863d976091dc95f39f2c78eb6b66c9c09de | 749d4566802c71fb1904bc554aa6357be9b61c39 | 48a4586 | 749d456 |
| 15 | 546e88b64c9e587507f257b0a835bee6bee67c7b | 5c44ab0e1d561d9f279098be96ec2396b8c7cc05 | 546e88b | 5c44ab0 |
| 16 | 958a815480f01d33ef5481438eb35f73dec241c8 | 76fd468f70bef3a2155c881ebbd1659f01d5f1c5 | 958a815 | 76fd468 |
| 17 | 5d3677c6e7c21072fce752e56e458cfb6a673b9d | 2077e31c9df7307706645e41072181a269ab5ced | 5d3677c | 2077e31 |
| 18 | 8c13fc2f452b67c097802886a6955b4d86bbccf0 | 5b1b632df5e48feda1ac35bc5c85725a6149e165 | 8c13fc2 | 5b1b632 |
| 19 | 316835fb73d66850444473c86fa33df10c4c8169 | a6726d2d317ce166e7c884a7ff06b0ea450d0423 | 316835f | a6726d2 |

Machine-readable copy: `agent-memory/evidence/git-stage2-rewrite-2026-09-05/sha-map.tsv`
(also: pre-rewrite metadata + verbatim messages + post-sync porcelain, same
directory). The live run reproduced the rehearsed dry-run chain
**bit-identically** (deterministic build; expected tip `a6726d2…` matched).
(MEASURED)

## 2. What changed and what did not (MEASURED, 21/21 mechanical PASS)

- 19 → 19 commits, same order, no merges introduced, one root, linear.
  Author AND committer on all 19: `juanz <204210901+el-informatico@users.noreply.github.com>`;
  author and committer DATES preserved.
- 18 messages replaced with the approved texts (independent 19/19 fidelity
  audit vs the Stage-1 proposal table); `88303b7`→`f067bcd` message unchanged,
  byte-verbatim. Zero `Co-Authored-By` trailers; zero word-bounded
  claude/chatgpt/generated-with/ai-assisted/robot-emoji strings; zero
  Ares-identity strings in metadata or messages.
- **Ranks 1–18 trees byte-identical to the originals** — deliberate
  (coherence-review amendment): the captured evidence that records the root
  as 22 files (task-contract-001:27, bootstrap-sanity:59) and the placed
  README sha256 `0b7f3bc5…` (decisions.md:73) remain TRUE at their referenced
  commits. Inter-commit patch-ids identical for ALL pairs 1→2 through 17→18.
- Rank 19 (`a6726d2`) is the single fold commit: +`LICENSE` (canonical Apache
  2.0, sha256 `cfc7749b96f63bd31c3c42b5c471bf756814053e847c10f3eb003417bc523d30`),
  README.md one line (`[MIT](LICENSE)` → the Apache/copyright line, mode
  preserved), and the three SHA remaps below. Full `git fsck` clean.
- range-diff note: not usable across the two chains (no common ancestor —
  the rewrite re-roots metadata from the same root tree); the equivalent
  proof is the per-rank tree-hash equality + patch-id equality above.

## 3. Reference repair (per the Stage-1 inventory, corrected this session)

- Inventory basis (independent recount): **188 refs / 19 files** (148 docs/ +
  40 agent-memory/), 25 in 7 tracked files, zero ambiguous; the Stage-1
  "165/125/40" totals were superseded (the +23 delta = the Stage-1 identity
  doc's post-inventory §8 addendum; tracked = 25 not 40).
- **Category A — remapped (3)**: `decisions.md:58` abac42a→`811df14`,
  `decisions.md:68` df44a8c→`2fbfab9`, `provider-feasibility-cerebras-gemini.md:455`
  958a815→`76fd468`. Verified present exactly once each; the three old shorts
  are absent from both files. (MEASURED)
- **Category B — intentionally preserved provenance (185 in the 19-file
  universe; 91 more in Stage-2-session files, all B; working-tree grand
  total 276)**: every other old-SHA occurrence — tracked evidence
  (impl-diff 14, orchestrator-audit 3, todo-verify-resolution 2,
  bootstrap-sanity 1 full, task-contract-001 1 full, decisions.md:162
  c1e0b0b) and all untracked dated docs/evidence incl. the Stage-1/Stage-2
  audit documents. The impl-diff/decisions.md/todo triple keeps ONE
  consistent treatment (preserve — remapping captured transcripts would
  falsify them). Pushed-tree census (`git grep` at `a6726d2`): old SHAs exist
  ONLY in the six intended tracked files, 22 occurrences total, zero
  elsewhere. (MEASURED)
- **Categories C/D — zero collisions**: no non-commit hash (blob, sha256,
  UUID, chatcmpl, foreign aresV2 `587e879f…`, orphaned `a70a83c`) matches or
  was altered; the new shorts appear nowhere except the remapped files and
  the map itself. (MEASURED)
- **Category E — ZERO, explicitly**: no unexplained stale commit-SHA
  reference remains, in the pushed tree or the working tree. Post-rewrite
  sweep matched the pre-derived oracle exactly (A 3 / B 185 / C 0 / D 0 /
  E 0). Count-label note: the checkpoint doc carries 14 B refs vs the
  oracle note's 13 — a derivation-label discrepancy only, class unchanged.
  (MEASURED)
- Documented dissents (coherence review): its MAJOR-1 (remap ALL agent-memory
  old SHAs incl. impl-diff's embedded original `git log`) and MAJOR-4
  (evidence docs describing the pre-rewrite `Ares Agent` identity) were
  REJECTED per the approved preserve-as-provenance policy and the inherent
  nature of an approved identity rewrite; its MAJOR-2/3 were ACCEPTED and
  produced the rank-19-only fold design. (OBSERVED/DOCUMENTED)

## 4. Non-commit hash preservation (MEASURED)

Blob-hash pairs in captured diffs (e.g. `a1cfc39`/`aa952d6`), sha256 evidence
digests (incl. the README placement digest `0b7f3bc5…`, still true at rank 4),
OTel conversation UUIDs, Groq `chatcmpl-<uuid>` prefixes, the foreign aresV2
SHA, and the orphaned pre-amend `a70a83c` — all byte-identical between the
backup-tip tree and the new-tip tree.

## 5. Test verification (MEASURED; classification per task)

- Working tree (with the uncommitted retry/fix work, which remains local and
  unpushed by decision D3): **132 passed** post-rewrite (5.38 s); segregation
  guard exit 0.
- Pushed tree (`a6726d2`'s committed tests = the `316835f`-era suite):
  **72 passed** (rehearsal clone; collection without `.env` fails
  environmentally — `evals/run_evals.py` builds the model at import — and a
  dummy-key offline run yields 72/72, matching the era's documented "72/72").
  **Correction recorded**: the checkpoint's "documented 94/94" figure
  described a working tree WITH the then-uncommitted fix, never a committed
  tree; the committed-tree figure is 72.
- No Stage-2 regressions: zero failures in either scope.

## 6. Recovery (OBSERVED)

`refs/heads/stage2-pre-rewrite-backup` = `316835fb73d66850444473c86fa33df10c4c8169`
holds the complete original chain (local-only; the push is exclusively
`git push origin main`; no tags exist). Backups + map persisted under
`agent-memory/evidence/git-stage2-rewrite-2026-09-05/`. The human may delete
the recovery ref after accepting the rewrite.
