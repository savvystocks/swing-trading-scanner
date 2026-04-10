Run the v3.1 swing trading research on the ticker(s) the user provided: $ARGUMENTS

Execute this bash command for each ticker, loading the EODHD_API_KEY from the Windows user environment:

```
cd "/c/Users/savva/OneDrive/Documents/Swing Trading" && export EODHD_API_KEY="69d8b4f4a14cc1.42263743" && python scripts/research.py <TICKER>
```

Then walk the user through the result in plain English, matching the detailed explanation style from the ENVA breakdown. For every pillar and gate, tell them:
- What the pillar/gate is checking
- What this specific stock's numbers look like
- Whether it passed, partially passed, or failed, and why
- Any concern or nuance specific to this setup (e.g. earnings within the hold window, low RVOL, sector concentration, squeeze already extended)

At the end, give an honest summary: is this a genuinely tradeable setup per the v3.1 spec, a watchlist-only name, or a clear reject. If there's any Tier-0 hard gate failure, explain which gate failed and why.

If the user passes a ticker without a market suffix, the script auto-appends `.US`. For LSE names they should include `.LSE` explicitly (e.g. `SHEL.LSE`, `RMV.LSE`).

If the user passes multiple tickers separated by spaces or commas, run each one separately and produce a ranked summary at the end from best setup to worst.
