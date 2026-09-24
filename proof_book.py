"""THE PROOF BOOK ("promotion 1"): a SECOND Alpaca paper account, $5,000, judged on its own.

Isolation is the whole point. Proof credentials live ONLY in GitHub Actions secrets - never on the
VPS, never in src/alpaca_creds.py's scan (which probes an account-agnostic endpoint and is
structurally incapable of telling two accounts apart). They are read here, explicitly, and every
cycle re-asserts that they open EXACTLY the pinned account and are not the discovery keys: a wrong
slot paste of two valid keys would otherwise trade the $864k book at proof size, or worse.

Records live in their own file (proof_logs.json), so the discovery sweeps - which list positions with
DISCOVERY creds and so cannot see this account at all - never meet them.

Every failure here is silent and total: no creds, no identity, no trade. A missed income week costs
about $26; an order in the wrong account costs the experiment.
"""
import json
import os
import urllib.request

import fade_book

LOG_PATH = "proof_logs.json"
_CHECK = {"done": False, "creds": None, "why": ""}


def cfg():
    return (fade_book.spec().get("proof_account") or {}) if fade_book.active() else {}


def account_number(creds):
    """The broker's own name for the account these keys open; None when they open nothing."""
    try:
        req = urllib.request.Request("https://paper-api.alpaca.markets/v2/account",
                                     headers={"APCA-API-KEY-ID": creds[0], "APCA-API-SECRET-KEY": creds[1]})
        with urllib.request.urlopen(req, timeout=15) as r:
            return json.loads(r.read()).get("account_number")
    except Exception:
        return None


def equity(creds):
    try:
        req = urllib.request.Request("https://paper-api.alpaca.markets/v2/account",
                                     headers={"APCA-API-KEY-ID": creds[0], "APCA-API-SECRET-KEY": creds[1]})
        with urllib.request.urlopen(req, timeout=15) as r:
            return float(json.loads(r.read()).get("equity") or 0)
    except Exception:
        return None


def verify(discovery_creds, pinned, getter=account_number):
    """(creds, reason). Creds only when they are present, distinct from discovery, and open the
    pinned account. Reason is always set, so the cycle log says why proof did nothing."""
    k = (os.environ.get("ALPACA_PROOF_API_KEY") or "").strip()
    s = (os.environ.get("ALPACA_PROOF_SECRET_KEY") or "").strip()
    if not (k and s):
        return None, "no proof credentials in the environment"
    if discovery_creds and all(discovery_creds) and (k, s) == (discovery_creds[0], discovery_creds[1]):
        return None, "PROOF KEYS ARE THE DISCOVERY KEYS - refusing (wrong-slot paste)"
    if not pinned:
        return None, "no account id pinned in the spec"
    acct = getter((k, s))
    if acct is None:
        return None, "proof credentials opened no account (rejected or unreachable)"
    if acct != pinned:
        return None, "proof credentials open a DIFFERENT account than the pinned one - refusing"
    return (k, s), "ok"


def creds(discovery_creds):
    """Verified once per process. Returns (creds_or_None, reason)."""
    if not _CHECK["done"]:
        _CHECK["creds"], _CHECK["why"] = verify(discovery_creds, (cfg().get("account_id") or "").strip())
        _CHECK["done"] = True
    return _CHECK["creds"], _CHECK["why"]


def load():
    try:
        d = json.load(open(LOG_PATH, encoding="utf-8"))
        return d if isinstance(d, list) else []
    except FileNotFoundError:
        return []
    except Exception:
        # FAIL CLOSED (2026-08-24 lesson): an unreadable book is BLIND, not empty. Returning [] here
        # would let the weekly gate re-arm and enter a second spread on top of a live one.
        raise


def save(data):
    json.dump(data, open(LOG_PATH, "w", encoding="utf-8"), indent=2, ensure_ascii=False)


def sample_equity(creds_, now, path=LOG_PATH.replace(".json", "_equity.jsonl")):
    """ONE equity row per UTC date, rewritten on every open-market cycle so it holds the session's LAST
    mark (~19:52 UTC), not the open (2026-09-24: sampled at the open the drawdown series lagged a day).
    The stint grammar (NORTH_STAR v1.7) measures its drawdown bound from daily equity, never from
    Friday-only marks, and the broker's equity is the only number that cannot be flattered by our own
    bookkeeping. Atomic replace: a sample that fails leaves the file exactly as it was."""
    day = now.date().isoformat()
    try:
        eq = equity(creds_)
        if eq is None:
            return False
        rows = []
        if os.path.exists(path):
            with open(path, encoding="utf-8") as fh:
                rows = [line.rstrip("\n") for line in fh if line.strip()]
        keep = [line for line in rows if ('"day": "' + day + '"') not in line]
        keep.append(json.dumps({"day": day, "ts_utc": now.isoformat(), "equity": round(eq, 2)}))
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            fh.write("\n".join(keep) + "\n")
        os.replace(tmp, path)
        return True
    except Exception:
        return False
