import os
import re
import ast
import sys
import json
import glob
import sqlite3
import subprocess
from datetime import datetime, timezone

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOCS = os.path.join(ROOT, "docs")
MAX_PART_CHARS = 1_500_000

SOURCE_EXT = {".py", ".yml", ".yaml", ".toml", ".sh", ".bat", ".ps1", ".sql", ".md"}
EXTRA_MAIN_WORKFLOWS = ["v10_lab.yml"]
EXTERNAL_ENTRYPOINTS = ["sandbox_proactive_lab.py", "poller.py"]

DB_PATH = os.path.join(ROOT, "data", "harvest.db")


def git(*a):
    return subprocess.run(["git", *a], cwd=ROOT, capture_output=True, text=True).stdout


def tracked():
    return [p for p in git("ls-files").splitlines() if p.strip()]


def read(p):
    try:
        with open(os.path.join(ROOT, p), encoding="utf-8", errors="replace") as f:
            return f.read()
    except Exception:
        return ""


def show_ref(ref):
    return subprocess.run(["git", "show", ref], cwd=ROOT, capture_output=True, text=True).stdout


def loc(text):
    return text.count("\n") + (1 if text and not text.endswith("\n") else 0)


CRED_PATTERNS = [
    ("anthropic_key", re.compile(r"""["'](sk-ant-[A-Za-z0-9_\-]{20,})["']""")),
    ("alpaca_key_id", re.compile(r"""["']((?:PK|AK)[A-Z0-9]{16,})["']""")),
    ("eodhd_token", re.compile(r"""["']([a-f0-9]{12,}\.[0-9]{6,})["']""")),
    ("openai_key", re.compile(r"""["'](sk-[A-Za-z0-9]{32,})["']""")),
    ("assigned_secret", re.compile(r"""(?i)(?:api[_-]?key|secret|token|passwd|password|bearer)\s*[=:]\s*["']([^"'\s]{16,})["']""")),
]
CRED_SAFE = re.compile(r"(?i)(os\.environ|getenv|secrets\.|example|redacted|your[_-]|xxxx|placeholder|<.*>)")


def scan_and_redact(path, text):
    findings = []
    out = text
    for kind, pat in CRED_PATTERNS:
        for m in pat.finditer(text):
            val = m.group(1)
            ctx = text[max(0, m.start() - 40):m.end() + 10]
            if CRED_SAFE.search(ctx):
                continue
            line = text[:m.start()].count("\n") + 1
            findings.append((path, line, kind, val[:6] + "..."))
            out = out.replace(val, "<<<REDACTED-HARDCODED-%s>>>" % kind.upper())
    return out, findings


ENV_PATTERNS = [
    re.compile(r"""os\.environ\.get\(\s*["']([A-Z][A-Z0-9_]+)["']"""),
    re.compile(r"""os\.environ\[\s*["']([A-Z][A-Z0-9_]+)["']"""),
    re.compile(r"""os\.getenv\(\s*["']([A-Z][A-Z0-9_]+)["']"""),
    re.compile(r"""getenv\(\s*["']([A-Z][A-Z0-9_]+)["']"""),
    re.compile(r"""secrets\.([A-Z][A-Z0-9_]+)"""),
    re.compile(r"""\$\{\{\s*secrets\.([A-Z][A-Z0-9_]+)"""),
]


def scan_env(text):
    found = set()
    for pat in ENV_PATTERNS:
        found.update(pat.findall(text))
    return found


URL_RE = re.compile(r"""https?://([A-Za-z0-9._\-]+)([A-Za-z0-9._\-/]*)""")
CLIENT_HINTS = {
    "Alpaca (alpaca-py + REST)": [r"paper-api\.alpaca", r"data\.alpaca", r"OptionHistoricalDataClient",
                                  r"get_option_latest_quote", r"get_option_chain", r"StockLatestQuoteRequest",
                                  r"/v2/positions", r"/v2/orders", r"/v2/account"],
    "Unusual Whales": [r"UnusualWhalesClient", r"flow_alerts", r"greek_exposure", r"darkpool",
                       r"net_prem_ticks", r"iv_rank", r"option_contract_historic"],
    "yfinance": [r"yfinance", r"yf\.Ticker", r"get_earnings_dates"],
    "EODHD": [r"eodhistoricaldata", r"eodhd\.com", r"EODHD"],
    "Telegram": [r"api\.telegram\.org", r"send_alert", r"sendMessage"],
    "Gmail SMTP": [r"smtp\.gmail\.com", r"smtplib"],
    "VADER (local)": [r"vaderSentiment", r"SentimentIntensityAnalyzer"],
}


def scan_apis(sources):
    hosts = {}
    hints = {k: set() for k in CLIENT_HINTS}
    for path, text in sources:
        for m in URL_RE.finditer(text):
            host = m.group(1)
            if host in ("localhost", "127.0.0.1") or host.endswith(".local"):
                continue
            hosts.setdefault(host, set()).add((m.group(1) + m.group(2))[:70])
        for prov, pats in CLIENT_HINTS.items():
            for pat in pats:
                if re.search(pat, text):
                    hints[prov].add(pat.replace("\\", ""))
    return hosts, hints


def resolve_module(mod, tset):
    base = mod.replace(".", "/")
    for cand in (base + ".py", base + "/__init__.py"):
        if cand in tset:
            return cand
    return None


def imported(pyrel):
    text = read(pyrel)
    try:
        tree = ast.parse(text)
    except Exception:
        return set()
    mods = set()
    pkg_parts = os.path.dirname(pyrel).split("/") if os.path.dirname(pyrel) else []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for n in node.names:
                mods.add(n.name)
        elif isinstance(node, ast.ImportFrom):
            if node.level and node.level > 0:
                up = pkg_parts[:len(pkg_parts) - (node.level - 1)] if node.level - 1 <= len(pkg_parts) else []
                base = "/".join(up)
                m = (base + "/" + node.module.replace(".", "/")) if node.module else base
                mods.add(m.strip("/").replace("/", "."))
                for n in node.names:
                    mods.add((m.strip("/") + "/" + n.name).replace("/", "."))
            elif node.module:
                mods.add(node.module)
                for n in node.names:
                    mods.add(node.module + "." + n.name)
    return mods


def entrypoints(files):
    eps = set()
    wf = [f for f in files if f.startswith(".github/workflows/")]
    for w in wf:
        for m in re.finditer(r"python(?:3)?\s+(?:-m\s+)?([A-Za-z0-9_./]+\.py)", read(w)):
            eps.add(m.group(1))
    sched = show_ref("origin/main:.github/workflows/v10_lab.yml")
    for m in re.finditer(r"python(?:3)?\s+(?:-m\s+)?([A-Za-z0-9_./]+\.py)", sched):
        eps.add(m.group(1))
    for e in EXTERNAL_ENTRYPOINTS:
        eps.add(e)
    for b in [f for f in files if f.endswith(".bat")]:
        for m in re.finditer(r"([A-Za-z0-9_./\\]+\.py)", read(b)):
            eps.add(m.group(1).replace("\\", "/").split("/")[-1] if "/" not in m.group(1) else m.group(1))
    return {e for e in eps if e in files}


def trace_live(eps, files):
    tset = set(files)
    live = set()
    stack = list(eps)
    while stack:
        f = stack.pop()
        if f in live or f not in tset:
            continue
        live.add(f)
        if f.endswith(".py"):
            for mod in imported(f):
                r = resolve_module(mod, tset)
                if r and r not in live:
                    stack.append(r)
    return live


def classify(files, live):
    STATE_JSON = {"proactive_sandbox_logs.json", "sandbox_ticker_cooloff.json",
                  "v10_tunable_parameters.json"}
    cls = {}
    for p in files:
        ext = os.path.splitext(p)[1].lower()
        base = os.path.basename(p)
        if p.startswith(".github/workflows/") and ext in (".yml", ".yaml"):
            cls[p] = "LIVE"
        elif p.startswith("data/") or ext in (".jsonl",) or base in STATE_JSON:
            cls[p] = "DATA"
        elif p.startswith("reports/") or ext == ".log" or ext == ".bak" or p.endswith("_log.md") \
                or "advisory" in base or base.startswith("HANDOFF") or base.endswith("_HANDOFF.md") \
                or p == "docs/codebase_reference.md" or p.startswith("docs/codebase_reference_part"):
            cls[p] = "GENERATED"
        elif p in live:
            cls[p] = "LIVE"
        elif ext in SOURCE_EXT:
            cls[p] = "LEGACY"
        else:
            cls[p] = "DATA"
    return cls


def db_section():
    if not os.path.exists(DB_PATH):
        return "_SQLite DB `data/harvest.db` not present in this checkout (local-only, gitignored)._\n"
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    out = ["```sql"]
    for r in con.execute("SELECT sql FROM sqlite_master WHERE sql IS NOT NULL ORDER BY type DESC, name"):
        out.append(r[0] + ";")
    out.append("```")
    out.append("")
    out.append("Row-count snapshot:")
    out.append("")
    out.append("| table | rows |")
    out.append("|---|---|")
    for r in con.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"):
        t = r[0]
        try:
            n = con.execute("SELECT COUNT(*) FROM \"%s\"" % t).fetchone()[0]
        except Exception:
            n = "?"
        out.append("| %s | %s |" % (t, n))
    con.close()
    return "\n".join(out) + "\n"


def sample_row(relglob, redactor=None):
    for f in sorted(glob.glob(os.path.join(ROOT, relglob)), reverse=True):
        for line in open(f, encoding="utf-8", errors="replace"):
            line = line.strip()
            if line:
                try:
                    obj = json.loads(line)
                except Exception:
                    continue
                return os.path.relpath(f, ROOT).replace("\\", "/"), obj
    return None, None


def data_formats():
    out = []
    rel, row = sample_row("data/harvest_inbox/*.jsonl")
    if row:
        keys = list(row.keys())
        if isinstance(row.get("features"), dict):
            row = {**row, "features": {"<28 metadata blocks>": "...", "_keys": list(row["features"].keys())}}
        out.append("**`data/harvest_inbox/candidates_YYYYMMDD.jsonl`** (one JSON object per line — the GHA-logger to local-poller transport). Source: `%s`. Fields (%d): %s" % (rel, len(keys), ", ".join(keys)))
        out.append("")
        out.append("```json")
        out.append(json.dumps(row, indent=2)[:3500])
        out.append("```")
    else:
        out.append("_No inbox JSONL present in this checkout._")
    out.append("")
    for label, path in [("`data/positions.json` (position-monitor state)", "data/positions.json"),
                        ("`proactive_sandbox_logs.json` (sandbox trade log — one record per cluster)", "proactive_sandbox_logs.json")]:
        fp = os.path.join(ROOT, path)
        if os.path.exists(fp):
            try:
                obj = json.load(open(fp, encoding="utf-8"))
                one = obj[0] if isinstance(obj, list) and obj else (next(iter(obj.values())) if isinstance(obj, dict) and obj else obj)
                out.append("**%s** — representative element (keys only for brevity):" % label)
                if isinstance(one, dict):
                    out.append("`" + ", ".join(list(one.keys())) + "`")
                out.append("")
            except Exception:
                pass
    return "\n".join(out) + "\n"


def build():
    files = tracked()
    eps = entrypoints(files)
    live = trace_live(eps, files)
    cls = classify(files, live)

    sources = []
    all_findings = []
    env_vars = set()
    for p in files:
        if os.path.splitext(p)[1].lower() in SOURCE_EXT:
            txt = read(p)
            red, finds = scan_and_redact(p, txt)
            all_findings.extend(finds)
            env_vars.update(scan_env(txt))
            sources.append((p, red, loc(txt), cls[p]))
    for p in [f for f in files if f.startswith(".github/workflows/")]:
        env_vars.update(scan_env(read(p)))
    env_vars.update(scan_env(show_ref("origin/main:.github/workflows/v10_lab.yml")))

    hosts, hints = scan_apis([(p, t) for p, t, _, _ in sources])

    branch = git("rev-parse", "--abbrev-ref", "HEAD").strip()
    sha = git("rev-parse", "--short", "HEAD").strip()
    src_loc = sum(l for _, _, l, _ in sources)
    now = datetime.now(timezone.utc)

    smap_path = os.path.join(DOCS, "system_map.md")
    if not os.path.exists(smap_path):
        os.makedirs(DOCS, exist_ok=True)
        open(smap_path, "w", encoding="utf-8").write(SYSTEM_MAP)
    system_map = open(smap_path, encoding="utf-8").read()

    H = []
    H.append("# Codebase reference — Swing Trading / V10 counterfactual-harvest system\n")
    H.append("| | |")
    H.append("|---|---|")
    H.append("| Generated (UTC) | %s |" % now.strftime("%Y-%m-%d %H:%M:%SZ"))
    H.append("| Repo | savvystocks/swing-trading-scanner |")
    H.append("| Branch | `%s` |" % branch)
    H.append("| Git SHA | `%s` |" % sha)
    H.append("| Tracked files | %d |" % len(files))
    H.append("| Source files dumped | %d |" % len(sources))
    H.append("| Source lines | %d |" % src_loc)
    H.append("| Generator | `scripts/make_reference.py` (re-run to regenerate) |")
    H.append("")
    H.append("> **Single-branch note:** the live system is one branch of this one repo — `main`. V9 was retired 2026-07-04; the V10 lab (`v10_lab.yml`) is the only engine. The only other repo is the private `harvest-snapshots` DB-backup repo. The barrier poller runs from `main` on the Vultr VPS.")
    H.append("")
    H.append("Classification method: **LIVE** = a workflow YAML, or a source file reachable by static import-trace (module + nested/lazy imports) from an actual entrypoint (GitHub Actions `run:` command, `v10_lab.yml`, or the VPS poller). **LEGACY** = a tracked source file not reached from any entrypoint. **DATA** = `data/`, `*.jsonl`, committed runtime-state JSON. **GENERATED** = tool output checked in (`reports/`, logs, advisories). Two caveats: dynamic/string-built imports can under-count LIVE (verify before deleting anything LEGACY); and non-code files are classified by the same execution-reachability rule, so an active doc such as `CLAUDE.md` reads LEGACY only because no entrypoint imports it — here LEGACY means 'outside the executable graph', not 'safe to delete'. Notably the entire V9 engine (`run_live_scan.py`, the `src/catalyst` ambush pipeline, `src/scanner.py` / `pillars.py`) was retired 2026-07-04, so those paths no longer exist in the tree.")
    H.append("\nEntrypoints traced: " + ", ".join("`%s`" % e for e in sorted(eps)))
    header = "\n".join(H) + "\n"

    tree = ["## Annotated repo tree\n"]
    counts = {"LIVE": 0, "LEGACY": 0, "GENERATED": 0, "DATA": 0}
    for p in files:
        counts[cls[p]] += 1
    tree.append("Totals — LIVE %d · LEGACY %d · GENERATED %d · DATA %d\n" % (counts["LIVE"], counts["LEGACY"], counts["GENERATED"], counts["DATA"]))
    lastdir = None
    for p in sorted(files):
        d = os.path.dirname(p) or "."
        if d != lastdir:
            tree.append("\n**%s/**" % d)
            lastdir = d
        tree.append("- `%s` — %s" % (os.path.basename(p), cls[p]))
    tree_s = "\n".join(tree) + "\n"

    dep = ["## Dependencies\n", "Python in use: `%s`\n" % sys.version.split()[0]]
    for rf in ["requirements.txt", "requirements-sandbox.txt", "pyproject.toml"]:
        if rf in files:
            dep.append("**%s**\n```\n%s\n```\n" % (rf, read(rf).strip()))
    dep_s = "\n".join(dep) + "\n"

    sch = ["## Schedules & triggers\n"]
    wfs = sorted([f for f in files if f.startswith(".github/workflows/")])
    for w in wfs:
        sch.append("### `%s` (branch `%s`)\n```yaml\n%s\n```\n" % (w, branch, read(w).strip()))
    smain = show_ref("origin/main:.github/workflows/v10_lab.yml")
    if smain.strip():
        sch.append("### `.github/workflows/v10_lab.yml` (branch `main` — harvest + paper trading)\n```yaml\n%s\n```\n" % smain.strip())
    sch.append("### Windows Task Scheduler (local host)\n`SwingHarvestPoller` → `run_poller.bat` → `python poller.py --once`. Weekdays 14:30 local, repeat every 15 min for 6h30m (09:30–16:00 ET). Holidays skipped via XNYS calendar in `poller.py`.\n")
    sch.append("### VPS crontab (poller migration) — **PENDING / NOT YET DONE**. The poller currently runs on the Windows host via Task Scheduler; no VPS crontab exists yet.\n")
    sch_s = "\n".join(sch) + "\n"

    api = ["## External surface\n", "### APIs called (by provider)\n"]
    for prov, pats in hints.items():
        if pats:
            api.append("- **%s** — %s" % (prov, ", ".join("`%s`" % x for x in sorted(pats))))
    api.append("\n### Outbound hosts seen in source (URL literals)\n")
    for host in sorted(hosts):
        api.append("- `%s` — e.g. %s" % (host, ", ".join("`%s`" % e for e in sorted(hosts[host])[:3])))
    api.append("\n### Environment variables / secrets read (NAMES ONLY — no values)\n")
    api.append(", ".join("`%s`" % v for v in sorted(env_vars)))
    api.append("")
    api_s = "\n".join(api) + "\n"

    sec = ["## Secret-bearing files & hardcoded-credential scan\n"]
    sec.append("Secret VALUES are never included. Secrets live only in: GitHub Actions secrets (see NAMES above), the Windows user environment, and the user's password manager. No `.env` file is tracked.\n")
    if all_findings:
        sec.append("**⚠ HARDCODED CREDENTIALS FOUND — redacted below, reported as security defects:**\n")
        sec.append("| file | line | type | prefix |")
        sec.append("|---|---|---|---|")
        for f, ln, k, pref in all_findings:
            sec.append("| `%s` | %d | %s | `%s` |" % (f, ln, k, pref))
    else:
        sec.append("**No hardcoded credentials detected** in any tracked source file (scanned for Anthropic/Alpaca/OpenAI/EODHD key shapes and `key=/secret=/token=/password=` literal assignments).")
    sec.append("")
    sec_s = "\n".join(sec) + "\n"

    db_s = "## Database\n\n" + db_section()
    data_s = "## Data interchange formats\n\n" + data_formats()

    meta = "\n---\n\n".join([header, "## System map (`docs/system_map.md`, inlined)\n\n" + system_map,
                             tree_s, dep_s, sch_s, api_s, sec_s, db_s, data_s,
                             "## FULL SOURCE\n\nEvery tracked source file below, verbatim (credentials redacted where found)."])

    file_sections = []
    for p, red, l, c in sources:
        fen = fence_for(red)
        file_sections.append((p, "\n### `%s`  —  %d lines  —  %s\n\n%s%s\n%s\n%s\n" % (
            p, l, c, fen, lang(p), red, fen)))

    return meta, file_sections, all_findings, len(files), src_loc, branch, sha


def fence_for(text):
    longest = 0
    for m in re.finditer(r"`+", text):
        longest = max(longest, len(m.group(0)))
    return "`" * max(3, longest + 1)


def lang(p):
    e = os.path.splitext(p)[1].lower()
    return {".py": "python", ".yml": "yaml", ".yaml": "yaml", ".toml": "toml",
            ".sh": "bash", ".bat": "bat", ".ps1": "powershell", ".sql": "sql", ".md": "markdown"}.get(e, "")


def write_bundle(meta, file_sections):
    os.makedirs(DOCS, exist_ok=True)
    total = len(meta) + sum(len(s) for _, s in file_sections)
    if total <= MAX_PART_CHARS:
        path = os.path.join(DOCS, "codebase_reference.md")
        open(path, "w", encoding="utf-8").write(meta + "\n" + "".join(s for _, s in file_sections))
        return [path], total
    parts = []
    cur = [meta]
    cur_len = len(meta)
    for p, s in file_sections:
        if cur_len + len(s) > MAX_PART_CHARS and len(cur) > 1:
            parts.append(cur)
            cur = []
            cur_len = 0
        cur.append(s)
        cur_len += len(s)
    if cur:
        parts.append(cur)
    file_to_part = {}
    idx = 1
    for part in parts:
        for chunk in part:
            m = re.search(r"### `([^`]+)`", chunk)
            if m:
                file_to_part[m.group(1)] = idx
        idx += 1
    index = ["\n## Part index (files by part)\n"]
    for f in sorted(file_to_part):
        index.append("- `%s` → part %d" % (f, file_to_part[f]))
    parts[0].insert(1, "\n".join(index) + "\n")
    written = []
    for i, part in enumerate(parts, 1):
        path = os.path.join(DOCS, "codebase_reference_part%d.md" % i)
        open(path, "w", encoding="utf-8").write("".join(part))
        written.append(path)
    return written, total


SYSTEM_MAP = """# System map — Swing Trading repo

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
"""


if __name__ == "__main__":
    meta, file_sections, findings, nfiles, sloc, branch, sha = build()
    written, total = write_bundle(meta, file_sections)
    print("=== bundle written ===")
    for w in written:
        print("  %s  (%d KB)" % (os.path.relpath(w, ROOT).replace("\\", "/"), os.path.getsize(w) // 1024))
    print("total chars: %d (%.2f MB) | parts: %d | threshold: %d" % (total, total / 1_048_576, len(written), MAX_PART_CHARS))
    print("hardcoded-credential findings: %d" % len(findings))
    for f in findings:
        print("  ", f)
    print("\n" + "=" * 70 + "\nHEADER\n" + "=" * 70)
    print(meta[:meta.find("\n---\n")].strip())
    print("\n" + "=" * 70 + "\nANNOTATED TREE\n" + "=" * 70)
    t0 = meta.find("## Annotated repo tree")
    t1 = meta.find("\n---\n", t0)
    print(meta[t0:t1].strip())
