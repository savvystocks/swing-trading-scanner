# Swing Trading Scanner — Project Memory

A daily automated scanner that screens S&P 500 + Russell 2000 + FTSE 100 + FTSE 250 (2784 tickers) against Savvas's v3.1 quantitative swing trading system and emails the ranked results. Built April 2026.

## What it does
Runs every weekday at 22:30 UTC via GitHub Actions. Pulls data from EODHD, computes all 7 pillars + 4 gates per ticker, scores into tiers 0-5, sends HTML email with per-pillar detail to savvastgeorgiou@gmail.com. Uses caching locally but CI runs fresh every day. Typical run: ~16 minutes, ~5200 API calls, 300-350 actionable candidates on a normal market day.

## Repo
- GitHub: https://github.com/savvystocks/swing-trading-scanner (private)
- Local: C:\Users\savva\OneDrive\Documents\Swing Trading
- Main branch only, no PR flow, push direct to main

## Key files
- `src/eodhd.py` — API client with 12h cache and retry
- `src/universe.py` — builds universe.json (rerun manually if needed, not in CI)
- `src/indicators.py` — SMA/EMA/RSI/MACD/ATR/BB math in pure pandas
- `src/pillars.py` — 7 pillars + 4 gates + helpers
- `src/scoring.py` — tier assignment, trade ticket builder
- `src/scanner.py` — main orchestrator with fast-filter → full-score pipeline
- `src/email_report.py` — jinja2 HTML email template + SMTP send
- `scripts/run_daily_scan.py` — entrypoint used by CI
- `.github/workflows/daily-scan.yml` — cron 22:30 UTC Mon-Fri
- `spec/v3.1-spec.md` — current active spec
- `spec/v3.0-original.md` — Savvas's original spec for reference
- `data/universe/universe.json` — committed, rebuilt only on manual universe.py run

## Secrets
Local Windows user env var: EODHD_API_KEY (set via setx)
GitHub repo secrets: EODHD_API_KEY, GMAIL_USER, GMAIL_APP_PASSWORD

## Cost model
One ongoing cost: EODHD All-in-One £99.99/mo. Everything else (GitHub Actions, Gmail SMTP) is free. CI uses ~300 of 2000 free minutes per month.

## Spec v3.1 decisions (vs v3.0 original)
- Gate 5 (options flow) demoted from hard gate to scoring modifier, scoped US-only. LSE names skip entirely. Bullish flow +0.5 tier, bearish -0.5.
- Pillar 7 insider-buying sub-signal scoped US-only. LSE names use short interest only via ShortPercentFloat.
- LSE tickers scored out of 6 pillars when Pillar 7 unavailable (no SI data). Tier thresholds scale: Tier 5 = 6/6, Tier 4 = 4/6, Tier 3 = 3/6.
- Pillar 6 for LSE drops analyst upgrade counts (AnalystRatings is US-only in EODHD) and relies on Earnings.History beat detection + Earnings.Trend revision counts, both of which DO populate for LSE.
- Canonical short interest field: `ShortPercentFloat`. The other SI fields (SharesShort, SharesShortPriorMonth, ShortRatio) return null for basically every ticker and are ignored.

## Hard gates (cause Tier 0 = no trade)
- Pillar 1 (Trend Template) FAIL
- Gate 4 (Catalyst Quality) FAIL — no Tier A or B catalyst found
- Gate 6 (Liquidity) FAIL — mcap < $500M OR dollar volume < $2M OR float < 30%
- Gate 7 (Earnings Blackout) FAIL — earnings within 10 days OR no history data at all

## Not hard gates
Gate 3 (RVOL) is an entry-timing signal not a rejection. A Tier 5 with low RVOL means "valid setup, wait for volume confirmation before clicking buy". Don't talk Savvas out of orders on Tier 5/low-RVOL names — Minervini pullback buys look exactly like that.

## Communication style
Savvas is not a coder. He gave me full coding control. He prefers plain text, clickable multiple choice over open questions, no markdown headers/bold walls, no emojis, no comments/docstrings in code unprompted, no unrequested tests. Load the savvas-coding-style skill at session start. Match his choices — if he picks an approach I'd argue against, execute it but flag it first with 2-4 alternatives.

## Lessons learned from the build

### Data source verification
- Don't trust docs alone for field population. EODHD docs say LSE has full fundamentals but AnalystRatings is silently missing for non-US. Always pull a real sample JSON before coding against a field.
- The EODHD `demo` token works for AAPL fundamentals and technical indicators endpoints — useful for schema verification without paying.
- Free tier only allows OHLCV/splits/dividends/exchanges/news. Everything else returns 403. Cannot verify fundamentals on free tier.
- Earnings.Trend keys are fiscal period-end dates (e.g. 2026-06-30), NOT announcement dates. For earnings blackout use Earnings.History[].reportDate field.
- ShortPercentFloat is the only reliable SI field in the entire schema.
- VIX symbol on EODHD is `VIX.INDX` — `^VIX` returns 404.
- SPY.US is the US benchmark, VUKE.LSE (Vanguard FTSE 100 ETF) is a clean UK benchmark proxy.
- Russell 2000 component tickers are NOT on Wikipedia. Use iShares IWM holdings CSV from blackrock.com.
- Wikipedia rejects default pandas/urllib User-Agent with 403. Set a browser UA header when scraping.

### Code traps I hit
- `if x is None or check` auto-passes when data is missing. Always write `if x is not None and check` unless explicitly want null to pass.
- Three silent-auto-pass bugs were in my first pass: Pillar 3 PEG null, Gate 6 float % null, Gate 7 empty history. Audit every `or None` in the pillar code.
- `inputs.scan_limit` on GitHub Actions cron trigger renders as empty string, not the workflow default. Handle empty with `isdigit()` guard before `int()`.
- Scraped website technical data (investing.com) can have wrong values. An STRL 200dMA was off by ~$80 which made me reject a Tier 5 setup. Only trust canonical API data.
- Gmail App Passwords UI returns "setting not available" when 2-Step Verification is not enabled yet. Enable 2SV first.

### Architecture decisions that paid off
- Fast filter on Pillar 1 + Pillar 4 (OHLCV only) before hitting fundamentals endpoint cut the full-score calls from 2784 to ~824. One fundamentals call per fast-filter survivor, not per universe ticker. Huge API savings.
- 12-hour cache on the EODHD client means local dev reruns are free. CI workspace is ephemeral so cache doesn't help there, but also doesn't hurt.
- Per-ticker try/except in scanner loop means one broken ticker can't crash the whole scan.
- GitHub Actions cron + upload-artifact gives a free history of every scan without needing a database.
- HTML email renders the full pillar+gate detail inline, no charts hosted anywhere, plain MIME attachment.

### Starting a session on this repo
1. Load savvas-coding-style skill
2. Check git log for recent activity
3. If making changes, test locally with `SCAN_LIMIT=30 SKIP_EMAIL=1` before pushing
4. Don't rebuild universe.json unless explicitly asked — it's committed
5. Push straight to main, no PRs, no branches

### What NOT to do
- Don't add comments, docstrings, type hints, or tests unprompted
- Don't refactor working code
- Don't use emojis
- Don't write README-style docs unless asked
- Don't trigger the live scanner or send emails from test runs — use SKIP_EMAIL=1 locally
