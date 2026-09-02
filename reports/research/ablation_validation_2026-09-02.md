# ABLATION VALIDATION - 2026-09-02

## A. Stability - enriched corpus (39.5k triggers), delta vs BASE at every cut
| block | wf60 | wf75 | wf85 | oof5 | verdict |
|---|---|---|---|---|---|
| IVX | +0.0178 | +0.0132 | +0.0126 | +0.0136 | CONFIRMED |
| PATH | -0.0034 | +0.0187 | +0.0089 | -0.0092 | MIXED |
| VOL | +0.0268 | +0.0145 | -0.0089 | +0.0116 | MIXED |

## B. Replication - 2-year corpus (66k trades, both bear episodes, different sampling; PATH not constructible here - needs print timestamps)
| block | wf60 | wf75 | wf85 | oof5 | verdict |
|---|---|---|---|---|---|
| IVX | -0.0246 | +0.0482 | +0.0145 | +0.0248 | MIXED |
| VOL | +0.0168 | +0.0204 | +0.0024 | +0.0209 | CONFIRMED |

## Combined verdicts
  PATH: MIXED on its only constructible corpus (stability exams)
  VOL: A=MIXED, B=see table - both corpora, both eras
  IVX: A=CONFIRMED, B=see table

Friday queue (owner 2026-09-03): PATH + VOL features wired into the nightly wide
student - training-side retro-compute plus live capture at entry; live capture
touches the harvest path so test_harvest_passivity is mandatory before push.
