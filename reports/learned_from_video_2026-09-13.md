# LEARNED FROM VIDEO - 2026-09-13

Source: "Lauren Tan workshop xAI Grokbot" (AI Agents for Business, published 2026-09-11, 59:41),
https://www.youtube.com/watch?v=ONeM6YDmvqA. Lauren Tan is a Cursor engineer (ex-Meta React
compiler, ex-Netflix). Owner's question: "I want more AI agents to make this system more effective;
let me know what you've learnt from it." Watched twice (Claude: captions + ten frames at the
moments the speaker points at the screen; Gemini: both halves in full) and reconciled; every
load-bearing item confirmed by both, one wording conflict settled from the frame.

## What the talk teaches
1. Trust in agents climbs a curve from one agent watched constantly to hundreds unattended, and
   there is no shortcut: the curve is your own verified trust, not the model's ability.
2. Verification is the first skill to build: the agent must be able to RUN the application and
   observe it (traces, DOM, simulator), otherwise the human is the verifier and the bottleneck.
3. A feature map, one file per feature from the user's point of view (what it is, how to get to
   it, how to drive it, preconditions, conventions, selectors), turns vague reports into
   reproducible work. Maintained mechanically, not by memory.
4. Skills are written from OBSERVED failure modes, one per failure, and tested with evals (rubric,
   disguised sub-agent directories, a judge of a different model, loop until the rubric is met).
5. Cloud agents on triggers pay off only after the local loop is trusted: "Benny" takes every bug
   report, reproduces it in its own environment, and posts "reproduced but already fixed on main".
6. Constraints beat review. Hardest layer first: codebase conventions, then static analysis and CI,
   then rules and bots, then skills, then a style guide. "Every time a human has to say it in
   review, turn it into a hard rule." The architecture makes the shortest path the correct path.
7. Tokens are an ROI question; she works where tokens are unlimited and says so.

## What already exists here in that shape
- Verification: the regime drill (15 scenarios with externals faked), the MOT (7 dimensions,
  180+ checks), the four harvest suites, the ship gate that refuses a red MOT.
- Hard rules from observed failures: BREAKDOWNS.md is append-only and every fix ships its
  regression check in the same commit (the "turn the review comment into CI" rule, since 2026-09-01).
- Adversarial review before entry-path changes: the six checks and the panels.
- Dead-man watchdogs that watch the DATA rather than exit codes.

## What was missing and is now built (owner's choice 2026-09-13 23:06)
- The feature map: `docs/feature_map/` (README + 13 subsystem files, seven sections each) and its
  lint `scripts/feature_map_lint.py`, wired into the gate as MOT 6.18.
- The skill `engine-feature-map` (~/.claude/skills) that makes every agent read the map first and
  run the subsystem's own verification instead of reasoning from the 200 KB engine file. Two
  independent reviewers failed this weekend for exactly the lack of this.

## What was deliberately not adopted
- Auto-merging agent PRs: incompatible with the gate and the owner's-word rules of a trading system.
- The "Benny" triage agent: never in the trade path, costs plan tokens per page; offered, declined
  for now.
- Cursor-specific tooling (control-glass, CDP port 9222, pstack, bugbot): the pattern transfers, the
  tools do not.
- A rewrite toward the Dune-style layout: three of its five rules already hold here (spec keys as
  the one writer, mechanical failure in the MOT, panels for exceptions); the engine being one file
  breaks "new work adds isolated files". Noted for the owner; a multi-day decision, not a weekend one.

## Claims not shown working
"1,000 PRs a month", "20 PRs auto-merged overnight", Benny's reproductions: numbers and
screenshots, not demonstrations. Treated as marketing until reproduced here.
