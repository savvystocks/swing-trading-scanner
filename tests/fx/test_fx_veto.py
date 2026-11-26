import json
import os
import subprocess
import tempfile
from datetime import datetime, timezone

import fxtest

TMP = tempfile.mkdtemp(prefix="fx_veto_test_")
os.environ["ALERT_DIR"] = TMP
os.environ["VETO_DIR"] = os.path.join(TMP, "veto")
os.environ["DRY_RUN"] = "1"
import pandas as pd

import fx_s26_alerts as A
import fx_veto_dossier as D
import fx_veto_run as V
import fx_veto_scoreboard as S

NY = "America/New_York"
H = 3600 * 10**9
VD = os.environ["VETO_DIR"]


def frame(rows):
    df = pd.DataFrame(rows, columns=["t", "bid_o", "bid_h", "bid_l", "bid_c", "ask_o", "ask_h", "ask_l", "ask_c"])
    df["t"] = df["t"].astype("int64")
    return df


def daily_market(days, start="2025-01-06", spread=0.0001, last_spread=None):
    rows = []
    for td, (o, h, l, c) in zip(pd.bdate_range(start, periods=len(days)), days):
        t0 = pd.Timestamp(td) - pd.Timedelta(hours=7)
        path = [(o, o, l, l), (l, h, l, h)] + [(c, c, c, c)] * 22
        for k, (mo, mh, ml, mc) in enumerate(path):
            t = (t0 + pd.Timedelta(hours=k)).tz_localize(NY).tz_convert("UTC").value
            rows.append([t] + [x - spread / 2 for x in (mo, mh, ml, mc)] + [x + spread / 2 for x in (mo, mh, ml, mc)])
    if last_spread:
        rows[-1][4], rows[-1][8] = rows[-1][4] - (last_spread - spread) / 2, rows[-1][8] + (last_spread - spread) / 2
    return A.Market(frame([tuple(x) for x in rows]))


BASE = (1.1000, 1.1030, 1.0970, 1.1005)


def signal_market(**kw):
    days = [BASE] * 40
    days[20] = (1.1000, 1.1030, 1.0900, 1.1005)
    days[30] = (1.0990, 1.1005, 1.0905, 1.1000)
    mk = daily_market(days[:31], **kw)
    s = mk.signal(30)
    tr = {"id": f"EUR_USD_{s['td']}", "pair": "EUR_USD", "dir": 1, "stop": s["stop"], "level": s["level"],
          "kind": s["kind"], "signal_td": s["td"], "sig_t": s["sig_t"], "entry_t": mk.entry_time(s["td"]),
          "status": "pending"}
    return mk, s, tr


def state(tr, guard=None, extra=()):
    return {"scanned": {}, "trades": list(extra) + [tr], **({"guard": guard} if guard else {})}


def test_dossier_carries_the_signal_card():
    mk, s, tr = signal_market()
    now = int(mk.t[-1]) + H
    d = D.build(mk, "EUR_USD", s, tr, state(tr), 100_000.0, 100_000.0, now)
    g = d["signal"]
    assert d["signal_id"] == "EUR_USD_2025-02-17" and d["schema"] == "s26_veto_dossier_v1"
    assert g["pair"] == "EUR_USD" and g["direction"] == "long" and g["signal_type"] == "pin bar"
    assert fxtest.near(g["level"], 1.0900) and fxtest.near(g["stop"], 1.0905) and g["last_price_side"] == "ask"
    assert fxtest.near(g["stop_distance_pips"], 95.5, 1e-6)
    assert fxtest.near(g["stop_distance_in_atrd"], round((1.10005 - 1.0905) / s["atrd"], 2))
    assert d["planned_entry"]["utc"] == d["order_deadline_utc"] == "2025-02-17T23:00:00Z"
    assert d["planned_entry"]["new_york"] == "Mon 2025-02-17 18:00" and d["planned_entry"]["tokyo"] == "Tue 2025-02-18 08:00"
    assert d["planned_entry"]["hold_window_start_utc"] == ["2025-02-17T23:00:00Z", "2025-02-18T23:00:00Z"]
    assert d["calendar"] == "calendar not available"
    json.dumps(d, allow_nan=False)


def test_dossier_has_the_last_sixty_daily_bars_and_a_summary():
    days = [BASE] * 70
    days[50] = (1.1000, 1.1030, 1.0900, 1.1005)
    days[60] = (1.0990, 1.1005, 1.0905, 1.1000)
    mk = daily_market(days[:61])
    s = mk.signal(60)
    tr = {"id": "EUR_USD_x", "pair": "EUR_USD", "dir": 1, "stop": s["stop"], "entry_t": mk.entry_time(s["td"]),
          "status": "pending"}
    b = D.build(mk, "EUR_USD", s, tr, state(tr), None, None, int(mk.t[-1]))["daily_bars_60"]
    assert len(b["bars"]) == 60 and b["bars"][-1] == [s["td"], 1.099, 1.1005, 1.0905, 1.1]
    assert b["summary"]["bars"] == 60 and b["summary"]["last"] == s["td"] and fxtest.near(b["summary"]["low"], 1.09)
    assert b["summary"]["largest_move_on"] == s["td"] and fxtest.near(b["summary"]["signal_day_range_in_atrd"],
                                                                        round(0.01 / s["atrd"], 2))


def test_dossier_spread_against_the_same_hour_median():
    mk, s, tr = signal_market(last_spread=0.0003)
    sp = D.build(mk, "EUR_USD", s, tr, state(tr), None, None, int(mk.t[-1]))["spread"]
    assert sp["last_h1_bar_new_york_hour"] == 16 and fxtest.near(sp["last_close_spread"], 3.0)
    assert fxtest.near(sp["median_same_new_york_hour"], 1.0) and fxtest.near(sp["ratio_last_to_same_hour_median"], 3.0)
    assert fxtest.near(sp["median_all_hours"], 1.0) and fxtest.near(sp["median_at_the_18_new_york_entry_open"], 1.0)


def test_dossier_open_positions_and_todays_pl():
    mk, s, tr = signal_market()
    other = {"id": "USD_JPY_y", "pair": "USD_JPY", "dir": -1, "stop": 151.2, "status": "open",
             "broker": {"status": "open", "units": -40_000, "fill": 150.0, "stop": 151.2, "tp": 147.6,
                        "risk_usd": 320.0, "fill_time": "2025-02-14T23:03:00Z"}}
    now = pd.Timestamp("2025-02-17 22:05", tz="UTC").value
    guard = {"B0": 100_000.0, "prague_day": "2025-02-17", "prague_ref": 100_200.0}
    d = D.build(mk, "EUR_USD", s, tr, state(tr, guard, [other]), 100_000.0, 99_200.0, now)
    a = d["account"]
    assert a["today_pl_usd"] == -1_000.0 and a["today_pl_pct_of_start"] == -1.0 and a["prague_midnight_balance"] == 100_200.0
    assert d["open_practice_positions"] == [{"id": "USD_JPY_y", "pair": "USD_JPY", "direction": "short", "units": -40_000,
                                             "fill": 150.0, "stop": 151.2, "take_profit": 147.6, "risk_usd": 320.0,
                                             "opened_utc": "2025-02-14T23:03:00Z"}]
    assert d["other_model_trades_pending_or_open"] == [{"id": "USD_JPY_y", "pair": "USD_JPY", "direction": "short",
                                                        "status": "open"}]


def test_dossier_without_an_account_read():
    mk, s, tr = signal_market()
    d = D.build(mk, "EUR_USD", s, tr, state(tr), None, None, int(mk.t[-1]))
    assert d["account"].startswith("account not available")


def test_dossier_written_once_to_the_veto_folder():
    mk, s, tr = signal_market()
    st = state(tr)
    p = D.write(TMP, mk, "EUR_USD", s, tr, st, None, None, int(mk.t[-1]))
    assert p == os.path.join(TMP, "veto", "EUR_USD_2025-02-17.dossier.json")
    first = open(p).read()
    D.write(TMP, mk, "EUR_USD", s, tr, st, 1.0, 1.0, int(mk.t[-1]) + H)
    assert open(p).read() == first and json.loads(first)["signal_id"] == "EUR_USD_2025-02-17"
    os.remove(p)


def test_a_failing_dossier_never_stops_the_alert():
    mk, s, tr = signal_market()
    keep = D.write
    D.write = lambda *a: 1 / 0
    try:
        A.veto_dossier(mk, "EUR_USD", s, tr, state(tr), None, None, int(mk.t[-1]))
    finally:
        D.write = keep
    ev = [json.loads(x) for x in open(A.EVENTS)][-1]
    assert ev["event"] == "veto_dossier_error" and ev["id"] == tr["id"] and ev["error"].startswith("ZeroDivisionError")


def test_the_order_path_never_reads_a_verdict():
    for f in ("fx_s26_alerts.py", "fx_risk_engine.py", "fx_oanda_orders.py"):
        src = open(os.path.join(fxtest.ROOT, "scripts", f), encoding="utf-8").read()
        assert "verdict" not in src and "fx_veto_run" not in src and "fx_veto_scoreboard" not in src, f


def cli(structured=None, subtype="success", is_error=False, extra=None):
    j = {"type": "result", "subtype": subtype, "is_error": is_error, "result": "", "num_turns": 2,
         "modelUsage": {"claude-opus-5-5": {"inputTokens": 10}}}
    if structured is not None:
        j["structured_output"] = structured
    j.update(extra or {})
    return json.dumps(j)


GOOD = {"decision": "approve", "confidence": 0.8, "reasons": ["no ground applies"]}


def test_parse_a_valid_approve_and_veto():
    v = V.parse(0, cli(GOOD))
    assert v == {"decision": "approve", "confidence": 0.8, "reasons": ["no ground applies"],
                 "models_used": ["claude-opus-5-5"], "num_turns": 2}
    v = V.parse(0, cli({"decision": "veto", "confidence": 1, "reasons": [" 1 thin holiday liquidity \n"]}))
    assert v["decision"] == "veto" and v["confidence"] == 1.0 and v["reasons"][0] == "1 thin holiday liquidity"


def test_parse_takes_a_fixed_form_answer_from_the_result_text_only_when_valid():
    assert V.parse(0, cli(extra={"result": json.dumps(GOOD)}))["decision"] == "approve"
    assert V.parse(0, cli(extra={"result": "I approve: " + json.dumps(GOOD)}))["decision"] == "no_verdict"
    assert V.parse(0, cli(extra={"result": json.dumps({**GOOD, "decision": "skip"})}))["decision"] == "no_verdict"


def test_parse_a_real_cli_auth_failure_is_no_verdict():
    out = json.dumps({"type": "result", "subtype": "success", "is_error": True, "num_turns": 1, "modelUsage": {},
                      "result": "Failed to authenticate. API Error: 401 OAuth access token is invalid."})
    v = V.parse(1, out)
    assert v["decision"] == "no_verdict" and "401" in v["error"] and v["models_used"] == []


def test_parse_malformed_output_is_no_verdict():
    for out in ("", "not json", "[1, 2]", None):
        v = V.parse(0, out)
        assert v["decision"] == "no_verdict" and "JSON" in v["error"], out


def test_parse_cli_errors_are_no_verdict():
    assert V.parse(1, cli(GOOD))["decision"] == "no_verdict"
    v = V.parse(0, cli(subtype="error_max_turns", is_error=True))
    assert v["decision"] == "no_verdict" and "error_max_turns" in v["error"]
    v = V.parse(1, cli(subtype="success", is_error=True, extra={"result": "Invalid bearer token"}))
    assert v["decision"] == "no_verdict" and "Invalid bearer token" in v["error"]


def test_parse_answers_outside_the_fixed_form_are_no_verdict():
    bad = [None, "approve", {"decision": "maybe", "confidence": 0.5, "reasons": ["x"]},
           {"decision": "veto", "confidence": 1.5, "reasons": ["x"]},
           {"decision": "veto", "confidence": True, "reasons": ["x"]},
           {"decision": "veto", "confidence": "0.5", "reasons": ["x"]},
           {"decision": "veto", "confidence": 0.5, "reasons": []},
           {"decision": "veto", "confidence": 0.5, "reasons": ["a", "b"]},
           {"decision": "veto", "confidence": 0.5, "reasons": ["line one\nline two"]},
           {"decision": "veto", "confidence": 0.5, "reasons": ["  "]},
           {"decision": "veto", "confidence": 0.5, "reasons": "x"},
           {"decision": "veto", "confidence": 0.5, "reasons": ["x"], "size": 0.5},
           {"decision": "veto", "reasons": ["x"]}]
    for b in bad:
        out = cli(b) if b is not None else cli()
        assert V.parse(0, out)["decision"] == "no_verdict", b


def test_command_is_read_only_structured_and_never_bare():
    c = V.command("PLAYBOOK")
    assert c[:2] == ["claude", "-p"] and "--bare" not in c
    for flag, val in (("--output-format", "json"), ("--tools", ""), ("--permission-mode", "dontAsk"),
                      ("--max-turns", "3"), ("--model", V.MODEL), ("--system-prompt", "PLAYBOOK")):
        assert c[c.index(flag) + 1] == val, flag
    assert "--strict-mcp-config" in c and json.loads(c[c.index("--json-schema") + 1]) == V.SCHEMA


def test_child_env_carries_the_subscription_token_and_no_api_key():
    keep = dict(os.environ)
    os.environ.update({"ANTHROPIC_API_KEY": "sk-x", "ANTHROPIC_AUTH_TOKEN": "y", "TELEGRAM_BOT_TOKEN": "z",
                       "CLAUDE_CODE_USE_BEDROCK": "1", "PATH": keep.get("PATH", "/usr/bin")})
    try:
        env = V.child_env("oauth-tok", "/tmp/cfg")
    finally:
        os.environ.clear()
        os.environ.update(keep)
    assert env["CLAUDE_CODE_OAUTH_TOKEN"] == "oauth-tok" and env["CLAUDE_CONFIG_DIR"] == "/tmp/cfg"
    assert not {"ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN", "TELEGRAM_BOT_TOKEN", "CLAUDE_CODE_USE_BEDROCK"} & set(env)


def test_veto_workflow_uses_the_oauth_secret_and_no_api_key():
    src = open(os.path.join(fxtest.ROOT, ".github", "workflows", "fx_s26_veto.yml"), encoding="utf-8").read()
    assert "CLAUDE_CODE_OAUTH_TOKEN: ${{ secrets.CLAUDE_CODE_OAUTH_TOKEN }}" in src
    assert "ANTHROPIC_API_KEY" not in src and "--bare" not in src and "[skip ci]" in src


def dossier(sid, deadline="2026-12-01T23:00:00Z"):
    os.makedirs(VD, exist_ok=True)
    p = os.path.join(VD, f"{sid}.dossier.json")
    with open(p, "w") as f:
        json.dump({"signal_id": sid, "order_deadline_utc": deadline}, f)
    return p


def at(s):
    return lambda: datetime.strptime(s, "%Y-%m-%d %H:%M").replace(tzinfo=timezone.utc)


PAGES = []


def runner(path, caller, clock=at("2026-12-01 22:20"), token="tok"):
    keep = os.environ.get("CLAUDE_CODE_OAUTH_TOKEN")
    os.environ["CLAUDE_CODE_OAUTH_TOKEN"] = token
    try:
        return V.run_one(path, caller=caller, version="2.1.326 (Claude Code)", notify=PAGES.append, clock=clock)
    finally:
        os.environ.pop("CLAUDE_CODE_OAUTH_TOKEN")
        if keep is not None:
            os.environ["CLAUDE_CODE_OAUTH_TOKEN"] = keep


def test_runner_writes_a_verdict_with_provenance():
    p = dossier("EUR_USD_2026-12-01")
    seen = []
    v = runner(p, lambda prompt, pb, tok: (seen.append((prompt, pb, tok)), (0, cli(GOOD, extra={}), ""))[1])
    assert v["decision"] == "approve" and v["before_order_time"] is True and v["verdict_utc"] == "2026-12-01T22:20:00Z"
    assert v["shadow"] is True and v["counted_toward_the_60"] is False and v["model_requested"] == V.MODEL
    assert v["cli_version"].startswith("2.1.326") and len(v["dossier_sha256"]) == len(v["playbook_sha256"]) == 64
    assert seen[0][0].startswith(V.FRAME) and '"EUR_USD_2026-12-01"' in seen[0][0] and seen[0][2] == "tok"
    assert seen[0][1].startswith("S26 PAPER VETO PLAYBOOK")
    assert json.load(open(p.replace(".dossier.", ".verdict."))) == v and V.pending(VD) == []
    assert runner(p, lambda *a: 1 / 0) is None


def test_runner_late_missing_token_timeout_and_no_cli_fail_open():
    def boom(e):
        def f(*a):
            raise e
        return f
    PAGES.clear()
    cases = [("EUR_USD_late", dict(caller=boom(AssertionError("must not run")), clock=at("2026-12-01 23:00")), "late"),
             ("EUR_USD_tok", dict(caller=boom(AssertionError("must not run")), token=""), "CLAUDE_CODE_OAUTH_TOKEN"),
             ("EUR_USD_slow", dict(caller=boom(subprocess.TimeoutExpired("claude", 300))), "no answer within"),
             ("EUR_USD_nocli", dict(caller=boom(FileNotFoundError("claude"))), "not found"),
             ("EUR_USD_junk", dict(caller=lambda *a: (0, "Error: oops", "")), "not JSON")]
    for sid, kw, msg in cases:
        v = runner(dossier(sid), **kw)
        assert v["decision"] == "no_verdict" and msg in v["error"], (sid, v)
    assert len(PAGES) == 5 and all("NO VERDICT" in x and "mechanical rule" in x for x in PAGES)
    assert runner(dossier("EUR_USD_late2"), boom(AssertionError()), clock=at("2026-12-02 01:00"))["before_order_time"] is False


def test_runner_broken_dossier_still_writes_no_verdict():
    os.makedirs(VD, exist_ok=True)
    p = os.path.join(VD, "EUR_USD_broken.dossier.json")
    with open(p, "w") as f:
        f.write("{not json")
    v = runner(p, lambda *a: (0, cli(GOOD), ""))
    assert v["decision"] == "no_verdict" and v["before_order_time"] is False and "JSONDecodeError" in v["error"]


def closed(sid, R, status="closed"):
    return {"id": sid, "pair": "EUR_USD", "dir": 1, "kind": "pin bar", "status": status,
            **({"R": R} if status == "closed" else {})}


def verdict(decision, before=True, conf=0.7):
    return {"decision": decision, "confidence": conf, "before_order_time": before}


def test_scoreboard_joins_and_splits_the_ledgers():
    trades = [closed("a", 2.0), closed("b", -1.0), closed("c", -1.01), closed("d", 2.0), closed("e", 0, "pending")]
    rows, pend = S.join(trades, {"b": verdict("veto"), "c": verdict("veto"), "a": verdict("approve")})
    assert pend == 1 and [r["decision"] for r in rows] == ["approve", "veto", "veto", "no_verdict"]
    m = S.summary(rows)
    assert m["signals"] == 4 and m["vetoes"] == 2 and m["no_verdict"] == 1 and m["approve"] == 1
    assert fxtest.near(m["raw_total_R"], 1.99) and fxtest.near(m["raw_R_per_signal"], 1.99 / 4)
    assert fxtest.near(m["vetoed_total_R"], 4.0) and fxtest.near(m["vetoed_R_per_signal"], 1.0)
    assert fxtest.near(m["vetoed_signals_R"], -2.01) and fxtest.near(m["random_veto_p"], 1 / 6)


def test_scoreboard_late_and_missing_verdicts_count_as_approved():
    trades = [closed("a", -1.0), closed("b", -1.0), closed("c", 0, "skipped")]
    rows, _ = S.join(trades, {"a": verdict("veto", before=False), "b": {"decision": "no_verdict", "error": "x"}})
    assert [r["decision"] for r in rows] == ["no_verdict", "no_verdict", "no_verdict"] and rows[2]["R"] == 0.0
    m = S.summary(rows)
    assert m["vetoes"] == 0 and m["random_veto_p"] is None and fxtest.near(m["vetoed_R_per_signal"], m["raw_R_per_signal"])


def test_scoreboard_report_is_labelled_shadow_and_prints_no_verdict():
    rows, pend = S.join([closed("a", 2.0), closed("b", -1.0)], {"b": verdict("veto")})
    out = S.report(rows, pend)
    assert out.splitlines()[0] == "S26 shadow - not counted toward the 60"
    assert "raw ledger" in out and "vetoed ledger" in out and "verdict: none" in out


def test_scoreboard_reads_the_paper_record_and_verdict_files():
    d = tempfile.mkdtemp(prefix="fx_veto_sb_")
    os.makedirs(os.path.join(d, "veto"))
    with open(os.path.join(d, "s26_state.json"), "w") as f:
        json.dump({"scanned": {}, "trades": [closed("EUR_USD_2026-12-01", -1.0)]}, f)
    with open(os.path.join(d, "veto", "EUR_USD_2026-12-01.verdict.json"), "w") as f:
        json.dump(verdict("veto"), f)
    trades, verdicts = S.load(os.path.join(d, "s26_state.json"), os.path.join(d, "veto"))
    assert len(trades) == 1 and verdicts["EUR_USD_2026-12-01"]["decision"] == "veto"


if __name__ == "__main__":
    fxtest.run(globals())
