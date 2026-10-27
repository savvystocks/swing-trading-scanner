"""Research desk tools: the code checks that keep agents from being the source of a number.
  hash FILE...                      sha256 of each file
  verify-lock PROTOCOL SHA_PREFIX   exit 1 unless the protocol's sha256 starts with the prefix the ledger recorded
  compare A.json B.json [RTOL]      compare the "primary" numbers of two result files (default 1% relative)
  provenance VERDICT EVIDENCE...    every number in the verdict must appear in an evidence file, else exit 1"""
import hashlib
import json
import re
import sys

NUM = re.compile(r"(?<![\w.])[-+]?\$?\d[\d,]*(?:\.\d+)?(?:[eE][-+]?\d+)?%?")
STRIP = [
    re.compile(r"\b\d{4}-\d{2}-\d{2}(?:[T ]\d{2}:\d{2}(?::\d{2})?Z?)?\b"),
    re.compile(r"\b\d{1,2}:\d{2}(?::\d{2})?\b"),
    re.compile(r"\b(?=[0-9a-f]*[a-f])(?=[0-9a-f]*\d)[0-9a-f]{7,64}\b"),
    re.compile(r"https?://\S+"),
    re.compile(r"`[^`]*`"),
    re.compile(r"(?m)^\s*(?:\d+\.|[-*])\s"),
    re.compile(r"(?m)^#+.*$"),
]


def sha(path):
    return hashlib.sha256(open(path, "rb").read()).hexdigest()


def numbers(text, strip=True):
    if strip:
        for rx in STRIP:
            text = rx.sub(" ", text)
    out = []
    for m in NUM.finditer(text):
        tok = m.group(0)
        raw = tok.replace("$", "").replace(",", "").rstrip("%")
        try:
            v = float(raw)
        except ValueError:
            continue
        dec = len(raw.split(".")[1]) if "." in raw and "e" not in raw.lower() else 0
        out.append((tok, v, dec))
    return out


def matches(v, dec, pool):
    tol = 0.5 * 10 ** -dec + 1e-12
    a = abs(v)
    for e in pool:
        for cand in (e, e * 100.0, e / 100.0):
            if abs(a - abs(cand)) <= tol:
                return True
    return False


def provenance(verdict, evidence):
    pool = set()
    for p in evidence:
        pool.update(v for _, v, _ in numbers(open(p, encoding="utf-8", errors="ignore").read(), strip=False))
    bad = []
    for tok, v, dec in numbers(open(verdict, encoding="utf-8").read()):
        if dec == 0 and 0 <= v <= 10:
            continue
        if not matches(v, dec, pool):
            bad.append(tok)
    if bad:
        print("PROVENANCE FAIL: numbers in the verdict found in no evidence file: " + ", ".join(sorted(set(bad))))
        return 1
    print(f"PROVENANCE OK: every number in {verdict} appears in the evidence ({len(evidence)} files)")
    return 0


def compare(a, b, rtol=0.01):
    pa, pb = json.load(open(a))["primary"], json.load(open(b))["primary"]
    ok = True
    for k in sorted(set(pa) | set(pb)):
        x, y = pa.get(k), pb.get(k)
        if not isinstance(x, (int, float)) or not isinstance(y, (int, float)):
            print(f"  {k}: {x} vs {y}  MISSING")
            ok = False
            continue
        good = abs(x - y) <= rtol * max(abs(x), abs(y), 1e-9)
        ok &= good
        print(f"  {k}: {x} vs {y}  {'match' if good else 'MISMATCH'}")
    print("REPRODUCED" if ok else "NOT REPRODUCED")
    return 0 if ok else 1


def main(argv):
    if not argv:
        print(__doc__)
        return 2
    cmd, rest = argv[0], argv[1:]
    if cmd == "hash":
        for p in rest:
            print(sha(p), p)
        return 0
    if cmd == "verify-lock":
        h = sha(rest[0])
        if h.startswith(rest[1].lower()):
            print(f"LOCK OK: {rest[0]} sha256 {h}")
            return 0
        print(f"LOCK BROKEN: {rest[0]} sha256 {h} does not start with {rest[1]}")
        return 1
    if cmd == "compare":
        return compare(rest[0], rest[1], float(rest[2]) if len(rest) > 2 else 0.01)
    if cmd == "provenance":
        return provenance(rest[0], rest[1:])
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
