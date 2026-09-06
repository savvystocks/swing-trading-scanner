# Governor scoreboard - 2026-W36

Authority changes by evidence only. The Governor demotes on RED within one cycle; it never
grants LIVE authority - that is the owner's switch (owner_promoted).

| organ | rung | state | green streak | authority | drift |
|---|---|---|---|---|---|
| council | CANDIDATE | AMBER | 0/6 | shadow | - |
| student | FROZEN | RED | 0/6 | shadow | - |

No organ is awaiting owner review; nothing is eligible for promotion this week.

Lifetime search intensity: **30,947 model/config trials** across all studies (feeds the deflated-Sharpe bar), plus the discovery rig's rule-search trials counted inside its own campaign PBO.

Demotions are automatic and immediate; promotions to LIVE require the owner to set
`owner_promoted` in governor_registry.json. The frozen V10 engine is unaffected by any state here.

## Measurement-lane trigger (report-only)

- Measurement-lane trigger: trigger not met. NOT MET - tight fills 175 >= floor 10; organic fills already cover where the school trades. fills by bucket={'med2-8': 204, 'tight<2': 175, 'wide8-20': 154, 'vwide>=20': 162}; school selects={'med2-8': 2425, 'tight<2': 2115, 'wide8-20': 437, 'vwide>=20': 78} [top-quintile-by-blend proxy (no TAKEs)]. Report-only; activation stays owner-gated (LIVE_GATE.md).