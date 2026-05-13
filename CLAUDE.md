# Swing Trading Scanner — Project Memory

A daily automated scanner that screens S&P 500 + S&P 400 MidCap + Russell 2000 + FTSE 100 + FTSE 250 (3089 tickers) against Savvas's v3.1 quantitative swing trading system and emails the ranked results. Built April 2026.

## Date discipline (CRITICAL — hard rule)

Before ANY time-sensitive analysis — CPI/FOMC/jobs/earnings/options expiry/position management/"trim now or hold" decisions — confirm the current date and day-of-week EXPLICITLY by running `date` first. Never say "tomorrow" or "today" or "next week" without verifying against the system clock. The UserPromptSubmit hook in ~/.claude/settings.json injects the date into every message, but if for any reason that's missing or stale, run `date` manually before timing-related advice. Getting a date wrong on a trading recommendation costs real money (one error in this project cost ~$710 in unrealized gains on an ENS option trim).

## What it does
Runs every weekday at 14:09 UTC via GitHub Actions (email arrives ~15:30 BST). Pulls data from EODHD, computes all 7 pillars + 4 gates per ticker, scores into tiers 0-5, sends an HTML Swing Scan email + a companion Priority Options Plays email to savvastgeorgiou@gmail.com. Uses caching locally but CI runs fresh every day. Typical run: ~21 minutes, ~5200 API calls, 300-350 actionable candidates on a normal market day.

## Repo
- GitHub: https://github.com/savvystocks/swing-trading-scanner (private)
- Local: C:\Users\savva\OneDrive\Documents\Swing Trading
- Main branch only, no PR flow, push direct to main

## Key files
- `src/eodhd.py` — API client with 24h cache and retry
- `src/universe.py` — builds universe.json (rerun manually if needed, not in CI)
- `src/indicators.py` — SMA/EMA/RSI/MACD/ATR/BB math in pure pandas
- `src/pillars.py` — 7 pillars + 4 gates + helpers
- `src/scoring.py` — tier assignment, trade ticket builder
- `src/scanner.py` — main orchestrator with fast-filter → full-score pipeline
- `src/email_report.py` — jinja2 HTML email template + SMTP send
- `scripts/run_daily_scan.py` — entrypoint used by CI
- `.github/workflows/daily-scan.yml` — cron 14:09 UTC Mon-Fri (email lands ~15:30 BST)
- `spec/v3.1-spec.md` — current active spec
- `spec/v3.0-original.md` — Savvas's original spec for reference
- `data/universe/universe.json` — committed, rebuilt only on manual universe.py run

## Secrets
- EODHD_API_KEY: stored ONLY as a Windows user env var (set via `setx`) and as a GitHub repo secret. NEVER write the literal token value into ANY committed file — EODHD's security scanner auto-revokes tokens it finds on GitHub. All-in-One subscription, Savvas's personal account, £99.99/mo, monthly billing to his card. 100,000 API call/MONTH quota (NOT per day — the credit pool resets at billing date, NOT at midnight UTC). Typical daily scan uses ~5,200 calls, so plan for ~6-7 scan-days of headroom per month. If you exhaust the quota mid-month, you'll get `402 Payment Required` on every endpoint (NOT 429 — EODHD uses 402 for quota top-up prompts). The fix is either a £5 top-up pack (100k extra credits) or wait for the next billing cycle. Account login: Google SSO via savvastgeorgiou@gmail.com.
- GMAIL_USER: `savvastgeorgiou@gmail.com` — scan emails sent from and to this address.
- GMAIL_APP_PASSWORD: stored only in GitHub repo secrets and Savvas's password manager. NEVER write the Gmail app password into this file or any committed file — it lives only in encrypted GitHub secrets.

## Cost model
One ongoing cost: EODHD All-in-One £99.99/mo + occasional £5 top-up packs if quota runs short. Everything else (GitHub Actions, Gmail SMTP) is free. CI uses ~300 of 2000 free minutes per month. EODHD MONTHLY quota: ~5,200 calls per scan × ~22 trading days = ~115k/mo gross. We trim with 24h client cache + non-duplicated factor screen + no email-job rescan to stay under the 100k/mo limit. If burn rate creeps up, the catalyst-email workflow no longer auto-rescans on missing JSON — it just alerts and exits, preserving credits.

## Schedule
Cron fires at 14:09 UTC Monday-Friday. Email arrives in Savvas's inbox around 15:30 BST (summer) / 14:30 GMT (winter). Data is yesterday's EOD bars — the time of day the cron fires is purely a delivery-time preference.

## Related projects
Savvas is also building a hyper-growth small-cap research project in a separate folder. Separate codebase, separate scope — if a session switches to that folder, load its own CLAUDE.md and don't carry assumptions from this repo.

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
- Fast filter on Pillar 1 + Pillar 4 (OHLCV only) before hitting fundamentals endpoint cuts the full-score calls from 3089 to ~900. One fundamentals call per fast-filter survivor, not per universe ticker. Huge API savings.
- 24-hour cache on the EODHD client means local dev reruns are free. CI workspace is ephemeral so cache doesn't help there, but also doesn't hurt.
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
