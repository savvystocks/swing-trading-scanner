"""Weekly brain run: snapshot -> Foundry (incremental) -> Harness -> report -> Telegram one-liner.
Runs on GitHub's machines against the snapshot COPY - nothing on the VPS or the live path.

Self-contained: it does NOT import src.telegram (isolation). CLI:
    python -m src.brain.run_weekly --snapshot <dir-or-gz> --out <workdir> --reports reports/v12_weekly
"""
import os
import sys
import json
import time
import argparse
import urllib.request
import urllib.parse

from . import loader, foundry, report


def _telegram(text):
    tok = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat = os.environ.get("TELEGRAM_CHAT_ID")
    if not tok or not chat:
        return False
    try:
        data = urllib.parse.urlencode({"chat_id": chat, "text": text, "parse_mode": "HTML"}).encode()
        req = urllib.request.Request(f"https://api.telegram.org/bot{tok}/sendMessage", data=data)
        with urllib.request.urlopen(req, timeout=15) as r:
            return json.loads(r.read().decode()).get("ok", False)
    except Exception:
        return False


def run(snapshot_source, out_dir, reports_dir, cache_dir=None, telegram=False):
    t0 = time.time()
    cache_dir = cache_dir or out_dir
    os.makedirs(reports_dir, exist_ok=True)
    os.makedirs(cache_dir, exist_ok=True)

    snap = loader.load_snapshot(snapshot_source, workdir=os.path.join(out_dir, "snap"))

    weight_cache = _load_json(os.path.join(cache_dir, "weight_cache.json"))
    state = _load_json(os.path.join(cache_dir, "brain_state.json")) or {"prev_rows": 0}
    baseline_null = _load_json(os.path.join(cache_dir, "baseline_null_rates.json"))

    ds = foundry.build_dataset(snap, out_dir, cache=weight_cache, baseline_null_rates=baseline_null)
    rep = report.weekly_edge_report(ds, prev_rows=state.get("prev_rows", 0), runtime_s=time.time() - t0)

    # weekly ops self-test (owner decision 28): the VPS watchdog stamps watchdog_status.json into the
    # snapshots repo; render it here. Reads only the snapshot checkout - isolation intact.
    ops_line = "## Ops self-test (watchdog)\n\n- no watchdog_status.json in the snapshot repo (watchdog not deployed or not stamping)"
    if os.path.isdir(snapshot_source):
        wd = _load_json(os.path.join(snapshot_source, "watchdog_status.json"))
        if wd:
            ops_line = ("## Ops self-test (watchdog)\n\n- last stamp {ts} | market_open={mo} | "
                        "inbox-commit age {age}m | status **{st}**").format(
                ts=wd.get("ts_utc"), mo=wd.get("market_open"),
                age=wd.get("last_inbox_commit_age_min"), st=wd.get("status"))
    rep["markdown"] += "\n\n" + ops_line

    report_path = os.path.join(reports_dir, f"report_{ds['dataset_version']}.md")
    open(report_path, "w", encoding="utf-8").write(rep["markdown"])

    _save_json(os.path.join(cache_dir, "weight_cache.json"), ds["weight_cache"])
    _save_json(os.path.join(cache_dir, "baseline_null_rates.json"),
               {k: v["null_rate"] for k, v in ds["feature_dict"].items()})
    _save_json(os.path.join(cache_dir, "brain_state.json"), {"prev_rows": len(ds["df"])})

    s = rep["summary"]
    hit = f"{s['hit_rate']:.3f}" if s.get("hit_rate") is not None else "UNDERPOWERED"
    msg = (f"<b>V12 weekly</b> {ds['dataset_version']}: rows {s['rows']} (+{s['rows_added']}), "
           f"hit {hit}, SPRT {s['sprt']}, {rep['summary'].get('verdict')}, "
           f"{time.time() - t0:.0f}s")
    if telegram:
        _telegram(msg)
    return {"report_path": report_path, "summary": s, "markdown": rep["markdown"],
            "parquet_path": ds["parquet_path"], "telegram_msg": msg}


def _load_json(path):
    try:
        return json.load(open(path))
    except Exception:
        return None


def _save_json(path, obj):
    json.dump(obj, open(path, "w"), indent=2, default=str)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--snapshot", required=True)
    ap.add_argument("--out", default="brain_work")
    ap.add_argument("--reports", default="reports/v12_weekly")
    ap.add_argument("--telegram", action="store_true")
    a = ap.parse_args()
    out = run(a.snapshot, a.out, a.reports, telegram=a.telegram)
    print(out["telegram_msg"])
    print("report ->", out["report_path"])
