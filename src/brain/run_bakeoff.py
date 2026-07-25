"""CLI: the strategy bake-off. Research only - recommends and deploys nothing.

    python -m src.brain.run_bakeoff --snapshot <dir-or-gz> --out <workdir> --reports reports/research
"""
import os
import json
import argparse
import numpy as np

from . import loader, foundry, discovery as D, convergence as CV, council as C, bakeoff as B


def _regime_of(cands, ids):
    """Reconstructed IV-regime proxy from the stored features (the engine's own regime LABEL is not
    stored per harvested candidate - this is a proxy and is labelled as such)."""
    iv = {}
    for cid in ids:
        f = cands[cid].get("features")
        v = None
        if f:
            try:
                j = json.loads(f) if isinstance(f, str) else f
                v = ((j.get("iv_term") or {}).get("iv_ratio")
                     or (j.get("vrp") or {}).get("front_iv")
                     or (j.get("macro") or {}).get("vix"))
            except Exception:
                v = None
        iv[cid] = float(v) if isinstance(v, (int, float)) else np.nan
    vals = np.array([iv[c] for c in ids], float)
    fin = np.isfinite(vals)
    if fin.sum() < 50:
        return {c: "unknown" for c in ids}, None
    med = float(np.nanmedian(vals[fin]))
    return {c: ("high_iv" if np.isfinite(iv[c]) and iv[c] >= med else
                "low_iv" if np.isfinite(iv[c]) else "unknown") for c in ids}, med


def run(snapshot_source, out_dir, reports_dir, with_gating=True):
    os.makedirs(reports_dir, exist_ok=True)
    snap = loader.load_snapshot(snapshot_source, workdir=os.path.join(out_dir, "snap"))
    cands, paths, weights, pairs, cluster_of = B.load_frame(snap["db_path"])
    n_exec = sum(1 for c in cands.values() if c.get("executed") == 1)
    print(f"universe: {len(cands)} candidates with usable paths | {len(pairs)} synthesized strike pairs"
          f" | {n_exec} executed rows (entry_ref is a MODEL premium for these - flagged, not trusted)")

    trials = D.Trials()
    per_structure = {}          # name -> [(cid, ts, ret, usd)]

    def add(name, rows):
        trials.bump("bakeoff_structures")
        per_structure[name] = rows

    # ---- 1. naked long variants (whole universe) ----
    for label, (up, dn, hz) in {
        "1. naked long +30/-50 (baseline)": (0.30, -0.50, None),
        "1b. naked long +15/-30": (0.15, -0.30, None),
        "1c. naked long +10/-20": (0.10, -0.20, None),
        "1d. naked long, 2h mark-out": (None, None, 2),
    }.items():
        rows = []
        for cid, p in paths.items():
            c = cands[cid]
            r, usd = B.naked_long(c, p, up, dn, hz)
            rows.append((cid, c["signal_ts_utc"], r, usd))
        add(label, rows)

    # ---- 2/3. spread structures (strike-pair subset only) ----
    def pair_rows(fn, **kw):
        out = []
        for pr in pairs:
            res = fn(pr, cands, **kw)
            if res is not None:
                out.append((pr["signal"], cands[pr["signal"]]["signal_ts_utc"], res[0], res[1]))
        return out

    add("2. debit spread (with flow), hold", pair_rows(B.debit_spread))
    add("2b. debit spread +50/-50", pair_rows(B.debit_spread, up=0.50, dn=-0.50))
    add("3. credit spread (FADE flow), hold", pair_rows(B.credit_spread_fade))
    add("3b. credit spread (FADE) +50/-100", pair_rows(B.credit_spread_fade, tp=0.50, sl=-1.00))

    # ---- 5. regime-conditioned (structures 2 and 3, high vs low IV) ----
    regime, med = _regime_of(cands, list(cands.keys()))
    for base_name, base_rows in list(per_structure.items()):
        if not base_name.startswith(("2.", "3.")):
            continue
        for rg in ("high_iv", "low_iv"):
            sub = [r for r in base_rows if regime.get(r[0]) == rg]
            if len(sub) >= 40:
                add(f"5. {base_name.split('.')[0]}. {rg}: " + base_name.split(" ", 1)[1], sub)

    # ---- model-GATED variants: genuine purged out-of-fold selection ----
    gate_note = "not run"
    if with_gating:
        try:
            ds = foundry.build_dataset(snap, out_dir)
            fb, X, kept, meta = CV.prepare_frame(ds, snap["db_path"])
            fb["net_ret"] = fb["realized_return"] - fb["cost_base"]
            res = C.run_council(fb, X, kept, trials)
            blend, bar = res["blend"], res["contract_bar"]
            take_ids = set(fb["candidate_id"].to_numpy()[np.isfinite(blend) & (blend >= bar)])
            fade_ids = set(fb["candidate_id"].to_numpy()[np.isfinite(blend) & (blend <= 0.10)])
            gate_note = (f"Council OOF probabilities; TAKE set n={len(take_ids)}, "
                         f"low-probability FADE set n={len(fade_ids)}")
            base_long = per_structure["1. naked long +30/-50 (baseline)"]
            add("4g. GATED naked long (council TAKE, purged OOF)",
                [r for r in base_long if r[0] in take_ids])
            add("4h. GATED credit FADE (council says won't pay, purged OOF)",
                [r for r in per_structure["3. credit spread (FADE flow), hold"] if r[0] in fade_ids])
        except Exception as e:
            gate_note = f"gating skipped: {type(e).__name__}: {e}"

    # ---- evaluate everything against ONE global split point (structures must be comparable) ----
    all_ts = np.concatenate([np.array([r[1] for r in rows], float)
                             for rows in per_structure.values() if rows])
    split_ms = float(np.median(all_ts))
    evals = {n: B.evaluate_structure(n, rows, weights, split_ms, cluster_of)
             for n, rows in per_structure.items() if rows}
    pbo = B.pbo_over_structures(per_structure, weights)

    # ---- era split on the baseline (synthetic vs real spreads) ----
    era = {}
    for name in ("1. naked long +30/-50 (baseline)", "3. credit spread (FADE flow), hold"):
        rows = per_structure.get(name) or []
        for tag, sel in (("pre-07-09 (SYNTHETIC costs)", [r for r in rows if r[1] < B.REAL_SPREAD_SINCE_MS]),
                         ("post-07-09 (REAL costs)", [r for r in rows if r[1] >= B.REAL_SPREAD_SINCE_MS])):
            if len(sel) >= 30:
                era[f"{name} | {tag}"] = B.summarize([r[2] for r in sel], [r[3] for r in sel],
                                                     [weights.get(r[0], 1.0) for r in sel], tag)

    md = _render(evals, pbo, era, trials, len(cands), len(pairs), gate_note, med,
                 snap.get("dataset_version") or os.path.basename(str(snapshot_source)), n_exec)
    path = os.path.join(reports_dir, f"strategy_bakeoff_{_today()}.md")
    open(path, "w", encoding="utf-8").write(md)
    print(md)
    print("report ->", path)
    return {"report": path, "pbo": pbo}


def _today():
    import datetime
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")


def _row(s):
    if not s or not s.get("n"):
        return f"| {s.get('label', '?')} | 0 | — | — | — | — | {s.get('note', '')} |"
    return (f"| {s['label']} | {s['n']} | {s['n_eff']} | {s['hit_wt']:.3f} | {s['mean_wt']:+.3f} | "
            f"${s['total_usd']:,.0f} | {s['usd_per_trade']:+.1f}/trade |")


def _render(evals, pbo, era, trials, n_univ, n_pairs, gate_note, iv_med, ver, n_exec=0):
    L = [f"# Strategy bake-off — {_today()}", "",
         "Research only (Lane A). **No strategy here is recommended or deployed**; deployment is a "
         "separate governed decision. Snapshot: `" + str(ver) + "`.", "",
         "All figures use executable prices only (buy at the ask, mark/sell on the bid). The "
         "`independent bets` column is a cluster-aggregated effective sample size: a burst of "
         "near-identical bets on one ticker-day counts as roughly one bet.", "",
         "> **Corrected 2026-07-25 after adversarial verification.** Five independent agents attacked "
         "this backtest's arithmetic; four found real defects, all fixed before these numbers were "
         "produced: spread entry legs were priced at two different instants; the debit-spread payoff "
         "lacked a floor at zero (13.8% of trades booked mathematically impossible losses); the "
         "effective-sample-size formula returned the raw trade count; and each structure split at its "
         "own median, making the out-of-sample columns non-comparable. A fifth found that the harness's "
         "PBO statistic itself was not CSCV — see the note under the overfitting section.", "",
         f"- universe: **{n_univ:,}** candidates with usable non-stale paths",
         f"- synthesized strike pairs available for spread structures: **{n_pairs:,}**",
         f"- structures tested (each a counted trial): **{trials.counts.get('bakeoff_structures', 0)}**",
         "", "## (a) IN-SAMPLE — every structure on its whole applicable universe", "",
         "| structure | trades | independent bets | win rate (wt) | avg net (wt) | total P&L per $800 | per trade |",
         "|---|---|---|---|---|---|---|"]
    for n in sorted(evals):
        L.append(_row(evals[n]["in_sample"]))
    L += ["", "## (b) OUT-OF-SAMPLE — the later time half only (walk-forward)", "",
          "A structure chosen on early data and applied to later data. One that only worked in a "
          "single stretch is exposed here.", "",
          "| structure | trades | independent bets | win rate (wt) | avg net (wt) | total P&L per $800 | per trade |",
          "|---|---|---|---|---|---|---|"]
    for n in sorted(evals):
        L.append(_row(evals[n]["oos_late_half"]))
    L += ["", "## Overfitting statistics across the structure SET", "",
          "> The PBO implementation was **rewritten on 2026-07-25**: the previous version selected the "
          "winner on a row and ranked that same row, with no train/test separation. On pure-noise "
          "matrices it returned ~0.01 ('certainly not overfit') where correct CSCV returns ~0.53 — it "
          "would have certified a fluke. Numbers below use real CSCV (winner chosen on train rows, "
          "ranked among trials on held-out rows).", "",
          f"- **PBO (probability the best structure is a fluke): {pbo.get('pbo')}** {pbo.get('pbo_note', '')}",
          f"- Deflated Sharpe of the champion: {pbo.get('dsr')} {pbo.get('dsr_note', '')}",
          f"- champion by mean P&L across time groups: `{pbo.get('champion')}` "
          f"(of {pbo.get('n_structures')} structures with coverage)",
          "", "PBO and deflated Sharpe belong to the SEARCH, not to any single rule: they answer "
          "'if I pick the best of these, how likely is it luck?'", ""]
    if era:
        L += ["## Cost-realism split (synthetic vs real spreads)", "",
              "| structure / era | trades | independent bets | win rate (wt) | avg net (wt) | total P&L | per trade |",
              "|---|---|---|---|---|---|---|"]
        for k, s in era.items():
            L.append("| " + k + " | " + _row(s).split("| ", 2)[2])
        L.append("")
    L += ["## What this data CANNOT honestly tell us", "",
          "- **3- and 5-day holds are NOT backtestable.** Stored option quotes cover ~1.6% of "
          "candidates at 3 trading days and ~0% at 5, because polling stops when a label resolves "
          "(~1 day median). Repricing with a constant-IV model would systematically overstate "
          "longer-hold returns (IV crush is a main reason these lose), so it was not done. The "
          "honest proxy is the underlying's own move at 3/5 days: 47–49% direction accuracy, "
          "negative mean (reports/discovery/stock_horizon_*.md).",
          "- **Spread structures cover only the strike-pair subset**, which skews to the most "
          "actively harvested, most liquid names — so spread rows flatter a fleet-wide spread "
          "strategy. Coverage is stated above; treat spread rows as an upper bound.",
          "- **Credit spreads assume close-before-expiry with no early assignment and no pin risk.** "
          "Quotes cannot model either; both are real risks absent from these numbers.",
          "- **Regime split uses a reconstructed IV proxy** (median IV ratio from stored features"
          + (f", median {iv_med:.3f}" if iv_med else "") + "), not the engine's own regime label, "
          "which is not stored per harvested candidate.",
          f"- **Model gating:** {gate_note}.",
          f"- **The engine's own {n_exec} executed rows carry a synthetic entry price.** For "
          "`executed=1` candidates `entry_ref` is a closed-form model premium x1.01 (the limit price "
          "sent to the broker), not the quote actually paid — found by adversarial verification "
          "2026-07-25. Those rows' measured returns are anchored on a price that was never traded. The "
          "fill ledger (live since the Phase-1 merge) records real fills and fixes this going forward; "
          "historical executed rows cannot be repaired in place.",
          "- **History is ~3 weeks of one broadly calm regime**, costs synthetic before 2026-07-09 "
          "and real after, and the label horizon resolves in ~1 day. Nothing here speaks to a "
          "volatile regime, a crash, or a multi-week hold.", ""]
    return "\n".join(L)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--snapshot", required=True)
    ap.add_argument("--out", default="bakeoff_work")
    ap.add_argument("--reports", default="reports/research")
    ap.add_argument("--no-gating", action="store_true")
    a = ap.parse_args()
    run(a.snapshot, a.out, a.reports, with_gating=not a.no_gating)
