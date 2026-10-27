# Research desk

A standing team of Claude agents that tests ideas. It never trades; its output is a protocol, a verdict and the
files behind them. Blueprint: C:/Users/savva/swing_research/agent_teams_2026-10/BLUEPRINT.md.

## Roles (.claude/agents/)
| Role | File | Job |
|---|---|---|
| Clerk | desk-clerk.md | finds earlier tests, drafts the protocol, writes the final one |
| Prior evidence | desk-prior-evidence.md | has it held up anywhere, out of sample, after costs |
| Data honesty | desk-data-honesty.md | look-ahead, survivorship, coverage, silent skips, multiple testing |
| Frictions | desk-frictions.md | fills, slippage, trade count, the $5,000 account rules |
| Crash risk | desk-crash-risk.md | worst year, worst fall, unobserved tails, the loss limits |
| Builder | desk-builder.md | implements the locked protocol, runs it once |
| Replicator | desk-breaker-replicator.md | rebuilds it from the protocol alone, blind |
| Auditor | desk-breaker-auditor.md | hunts the defect that makes the result false |
| Judge | desk-judge.md | verdict against the pre-set bar; numbers checked by code |

## How an idea goes through
1. research-desk-design (.claude/workflows/) with {idea, studyDir}: clerk intake, four blind reviews, final protocol.
   No outcome data is read.
2. The calling session runs `python .claude/desk/desk_tools.py hash <studyDir>/PROTOCOL.md`, ships the ledger row
   through the gate, and the owner sees it.
3. research-desk-measure with {studyDir, protocolSha}: builder, then replicator and auditor in parallel, then judge.
   mode "audit" judges existing code and results instead of building.
4. The judge's VERDICT.md must pass `desk_tools.py provenance`. The owner decides what happens next.

When the Workflow tool is switched off in a session, the calling session runs the same steps by hand with the Agent
tool: one general-purpose agent per role, each told to read its role file first, in the same order, with the same
blinding (the replicator never sees the builder's code or results; reviewers never see each other's work).

## Known limits
- Every agent sees the project memory index (probe 2026-10-27). It knows past conclusions, which helps the clerk and
  can anchor the others. Known-answer tests must use cases whose answers are not in memory, and nothing about a test
  case goes into memory until the test is scored.
- desk_tools.py provenance checks that each number in a verdict appears in an evidence file; it cannot check that the
  number is used for the right thing. The judge's role file and the owner's reading cover that.
- New role files load at the start of a session; in the session that created them they are used through
  general-purpose agents told to read the file. In that hand-run mode the tool list in a role file is not enforced
  (the frictions reviewer fetched web pages although its role lists none), so the house rules carry the limits.
