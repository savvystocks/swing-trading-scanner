"""S26 paper veto in shadow (NORTH_STAR v1.10, clauses C13-C15, V1, V4). For each dossier in reports/fx_alerts/veto
without a verdict, asks Claude headless under the frozen PLAYBOOK.md, on the owner's subscription token only (the
environment it passes holds no API key), with no tools and no MCP servers, for one structured APPROVE or VETO, and
writes <signal id>.verdict.json next to the dossier, never overwritten. Any failure, a late run included, writes
decision "no_verdict" (fail open: the signal stands as the mechanical rule) and pages. No order reads a verdict."""
import glob
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import urllib.parse
import urllib.request
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VETO_DIR = os.environ.get("VETO_DIR", os.path.join(ROOT, "reports", "fx_alerts", "veto"))
PLAYBOOK = os.path.join(ROOT, "reports", "fx_alerts", "veto", "PLAYBOOK.md")
MODEL = os.environ.get("VETO_MODEL", "claude-opus-5-5")
TIMEOUT = 300
SCHEMA = {"type": "object", "additionalProperties": False, "required": ["decision", "confidence", "reasons"],
          "properties": {"decision": {"type": "string", "enum": ["approve", "veto"]},
                         "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                         "reasons": {"type": "array", "minItems": 1, "maxItems": 1,
                                     "items": {"type": "string", "minLength": 1, "maxLength": 200}}}}
FRAME = "One S26 signal dossier follows (JSON, built by code). Give your verdict in the required structured form.\n\n"
KEEP_ENV = ("PATH", "HOME", "USER", "LANG", "LC_ALL", "TMPDIR", "TEMP", "TMP", "SYSTEMROOT", "WINDIR", "USERPROFILE",
            "APPDATA", "LOCALAPPDATA", "COMSPEC", "PATHEXT")


def utc_iso(dt):
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_iso(s):
    return datetime.strptime(s, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)


def sha(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def command(playbook):
    return ["claude", "-p", "--model", MODEL, "--output-format", "json", "--json-schema", json.dumps(SCHEMA),
            "--tools", "", "--strict-mcp-config", "--permission-mode", "dontAsk", "--max-turns", "3",
            "--no-session-persistence", "--system-prompt", playbook]


def child_env(token, config_dir):
    env = {k: os.environ[k] for k in KEEP_ENV if k in os.environ}
    env.update({"CLAUDE_CODE_OAUTH_TOKEN": token, "CLAUDE_CONFIG_DIR": config_dir, "DISABLE_AUTOUPDATER": "1"})
    return env


def call_claude(prompt, playbook, token):
    with tempfile.TemporaryDirectory(prefix="s26_veto_") as cwd:
        p = subprocess.run(command(playbook), input=prompt, capture_output=True, text=True, encoding="utf-8",
                           timeout=TIMEOUT, cwd=cwd, env=child_env(token, os.path.join(cwd, "config")))
    return p.returncode, p.stdout, p.stderr


def no_verdict(error, **meta):
    return {"decision": "no_verdict", "error": error, **meta}


def form_problem(v):
    if not isinstance(v, dict):
        return "structured output missing or not an object"
    if set(v) != {"decision", "confidence", "reasons"}:
        return f"answer outside the fixed form (keys {sorted(v)})"
    if v["decision"] not in ("approve", "veto"):
        return f"decision outside the fixed form: {str(v['decision'])[:40]}"
    c = v["confidence"]
    if isinstance(c, bool) or not isinstance(c, (int, float)) or not 0 <= c <= 1:
        return f"confidence outside 0-1: {str(c)[:40]}"
    rs = v["reasons"]
    if not isinstance(rs, list) or len(rs) != 1 or not isinstance(rs[0], str) or not rs[0].strip() \
            or "\n" in rs[0].strip():
        return "reasons must hold exactly one one-line reason"
    return None


def parse(code, out, err=""):
    try:
        j = json.loads(out)
    except (TypeError, ValueError):
        return no_verdict(f"claude exit {code}, output is not JSON: {(err or out or '').strip()[:200]}")
    if not isinstance(j, dict):
        return no_verdict(f"claude exit {code}, output is not a JSON object")
    meta = {"models_used": sorted((j.get("modelUsage") or {}).keys()), "num_turns": j.get("num_turns")}
    if code != 0 or j.get("is_error") or j.get("subtype") != "success":
        return no_verdict(f"claude exit {code}, {j.get('subtype')}: {str(j.get('result', ''))[:200]}", **meta)
    v = j.get("structured_output")
    if v is None:
        try:
            v = json.loads(j.get("result") or "")
        except (TypeError, ValueError):
            v = None
    problem = form_problem(v)
    if problem:
        return no_verdict(problem, **meta)
    return {"decision": v["decision"], "confidence": float(v["confidence"]), "reasons": [x.strip() for x in v["reasons"]],
            **meta}


def cli_version():
    try:
        return subprocess.run(["claude", "--version"], capture_output=True, text=True, timeout=60).stdout.strip() or None
    except Exception:
        return None


def page(text):
    tok, chat = os.environ.get("TELEGRAM_BOT_TOKEN", ""), os.environ.get("TELEGRAM_CHAT_ID", "")
    if not tok or not chat:
        print("telegram secrets missing; page not sent")
        return
    try:
        data = urllib.parse.urlencode({"chat_id": chat, "text": text}).encode()
        urllib.request.urlopen(f"https://api.telegram.org/bot{tok}/sendMessage", data=data, timeout=30)
    except Exception as e:
        print("telegram page failed:", type(e).__name__)


def pending(veto_dir=None):
    d = veto_dir or VETO_DIR
    return sorted(p for p in glob.glob(os.path.join(d, "*.dossier.json"))
                  if not os.path.exists(p[:-len(".dossier.json")] + ".verdict.json"))


def now_utc():
    return datetime.now(timezone.utc)


def run_one(path, caller=call_claude, version=None, notify=page, clock=now_utc):
    sid = os.path.basename(path)[:-len(".dossier.json")]
    vpath = path[:-len(".dossier.json")] + ".verdict.json"
    if os.path.exists(vpath):
        return None
    base = {"signal_id": sid, "shadow": True, "counted_toward_the_60": False, "model_requested": MODEL,
            "cli_version": version, "schema_sha256": sha(json.dumps(SCHEMA))}
    try:
        with open(PLAYBOOK, encoding="utf-8") as f:
            playbook = f.read()
        with open(path, encoding="utf-8") as f:
            text = f.read()
        base["playbook_sha256"], base["dossier_sha256"] = sha(playbook), sha(text)
        deadline = parse_iso(json.loads(text)["order_deadline_utc"])
        base["order_deadline_utc"] = utc_iso(deadline)
        token = os.environ.get("CLAUDE_CODE_OAUTH_TOKEN", "")
        if clock() >= deadline:
            v = no_verdict("late: the veto ran at or after the order time")
        elif not token:
            v = no_verdict("CLAUDE_CODE_OAUTH_TOKEN missing")
        else:
            v = parse(*caller(FRAME + text, playbook, token))
    except subprocess.TimeoutExpired:
        v = no_verdict(f"claude gave no answer within {TIMEOUT} s")
    except FileNotFoundError as e:
        v = no_verdict(f"not found: {str(e)[:150]}")
    except Exception as e:
        v = no_verdict(f"{type(e).__name__}: {str(e)[:200]}")
    done = clock()
    v.update(base)
    v["verdict_utc"] = utc_iso(done)
    v["before_order_time"] = "order_deadline_utc" in base and done < parse_iso(base["order_deadline_utc"])
    with open(vpath, "x", encoding="utf-8") as f:
        json.dump(v, f, indent=1)
    if v["decision"] == "no_verdict":
        notify(f"S26 veto (shadow): NO VERDICT for {sid} - {v['error'][:160]}. Nothing changes: the signal stands as "
               f"the mechanical rule, logged as no verdict.")
    return v


def main():
    todo = pending()
    if "--pending" in sys.argv:
        print(f"count={len(todo)}")
        return
    version = cli_version() if todo else None
    for p in todo:
        v = run_one(p, version=version)
        if v:
            print(f"{v['signal_id']}: {v['decision']}")
    print(f"{len(todo)} dossier(s) handled")


if __name__ == "__main__":
    main()
