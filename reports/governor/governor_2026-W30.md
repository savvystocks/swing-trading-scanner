# Governor scoreboard - 2026-W30

Authority changes by evidence only. The Governor demotes on RED within one cycle; it never
grants LIVE authority - that is the owner's switch (owner_promoted).

| organ | rung | state | green streak | authority | drift |
|---|---|---|---|---|---|
| council | CANDIDATE | AMBER | 0/6 | shadow | - |
| student | CANDIDATE | AMBER | 0/6 | shadow | - |

No organ is awaiting owner review; nothing is eligible for promotion this week.

Demotions are automatic and immediate; promotions to LIVE require the owner to set
`owner_promoted` in governor_registry.json. The frozen V10 engine is unaffected by any state here.

## Measurement-lane trigger (report-only)

- Measurement-lane trigger: trigger not met. NOT YET EVALUABLE - only 0 real entry fills (need >= 20). fills by bucket=none; school selects={'med2-8': 887, 'tight<2': 728, 'wide8-20': 97, 'vwide>=20': 18} [top-quintile-by-blend proxy (no TAKEs)]. Report-only; activation stays owner-gated (LIVE_GATE.md).