# System map — Swing Trading repo

One engine on one branch (`main`). V9 was retired 2026-07-04; the counterfactual-harvest / V10 lab is the whole live system.

## The engine — V10 Proactive Lab + Counterfactual Harvest
Autonomous paper-options-trading data lab, on branch `main` — the whole live system (V9 retired 2026-07-04).

Flow:
1. **Scan** — `sandbox_proactive_lab.scan_candidates` pulls whole-market Unusual Whales option flow
   (600 rows/cycle), filters to the affordable band (per-contract $0.30–$4.00 = 2 contracts on the
   $800/trade budget), ranks by flow premium.
2. **Trade** — `enter_proactive_set` routes one directional Call/Put per cycle to Alpaca **paper**,
   sizes to $800, manages exits via a state machine (`manage_exit`): +30% scale-out (50%),
   break-even shield, +50%→trailing halt (20% off peak), −50% stop, expiry exit. Exits are
   evaluated by the cron and fired as market closes (no server-side OCO/bracket orders).
3. **Harvest (Component 1)** — `harvest_logger.harvest_scan` (fail-open, post-trade) logs every
   scored candidate (executed + skipped) with a 37-feature payload for a bounded sample and cheap
   rows for the rest. Runs inside GitHub Actions, where the DB does not persist, so it appends rows
   to `data/harvest_inbox/candidates_YYYYMMDD.jsonl` and commits them back to `main`.
4. **Poll & label (Component 2)** — `poller.py --once` (on the Vultr VPS, from a crontab) pulls `main` and ingests the
   committed inbox into local SQLite (`data/harvest.db`), fetches option NBBO from Alpaca (UW
   fallback), appends `bid_path`, and resolves a triple-barrier label (`harvest_labeler.label_path`):
   up bid≥entry×1.30, down bid≤entry×0.50, signed vertical at min(week's last session 16:00 ET,
   expiry). Labels feed a future Phase-4 classifier.

## Schedules
- `v10_lab.yml` (main): cron `*/10 13-21 * * 1-5` + workflow_dispatch (incl. `flush`) +
  repository_dispatch; runs `main` directly, executes `sandbox_proactive_lab.py`, commits
  forensic logs + harvest inbox back to `main`.
- `health-check.yml` (main): weekly provider schema-drift harness (`schema_harness.py`).
- VPS crontab: `poller.py --once` (pulls `main` first) + a nightly off-box gzip DB backup to the
  private `harvest-snapshots` repo.

## Storage
- `data/harvest.db` — local-only SQLite (WAL), tables `candidates` / `bid_path` / `labels`, dated
  backups ×14, gitignored.
- `data/harvest_inbox/*.jsonl` — committed transport (GHA → local poller).
- `proactive_sandbox_logs.json`, `sandbox_ticker_cooloff.json`, `v10_tunable_parameters.json` —
  committed runtime state for the sandbox.

## External APIs
Unusual Whales (option flow, greeks, dark pool), Alpaca (paper trading + option/stock market data),
yfinance (fundamentals/earnings/VIX), Telegram (alerts), Gmail SMTP (optional poller summary),
VADER (local sentiment). EODHD does not exist for any purpose.

## Known gaps (see reports/harvest_audit_2026-07-02.md)
No server-side exit orders (Alpaca rejects OCO/bracket/trailing on options) — exits stay
cron-evaluated; the server-side-exit backstop is the open Phase-4 item. The git-pull, Friday-barrier,
and orphaned-position gaps were closed 2026-07-02/03/04.
