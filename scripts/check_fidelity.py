#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""check_fidelity.py -- prove that no line of dialogue was altered.

    python check_fidelity.py --source script.txt --data data.json
    python check_fidelity.py --source original.docx --data data.json --fix-report

Every k=L text in data.json must appear verbatim (whitespace-insensitive) in the
source script. Anything that does not is reported as a fidelity break, which
almost always means the model "helpfully" rewrote the dialogue. Run this before
building the page; treat a non-zero exit as a release blocker.

Exit codes: 0 all lines preserved, 1 fidelity break found, 2 usage / IO error.
"""
from __future__ import annotations

import argparse
import io
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

WS = re.compile(r"\s+")
# characters that differ only typographically between a docx and a hand-typed copy
FOLD = {
    "\u2018": "'", "\u2019": "'", "\u201c": '"', "\u201d": '"',
    "\u2013": "-", "\u2014": "-", "\u2212": "-", "\u00a0": " ",
    "\u3000": " ", "\u2026": "...",
}


def norm(s):
    s = str(s or "")
    for a, b in FOLD.items():
        s = s.replace(a, b)
    return WS.sub(" ", s).strip()


def load_source(path):
    ext = os.path.splitext(path)[1].lower()
    if ext == ".json":
        mod = __import__("extract_script")
        blocks = json.load(io.open(path, encoding="utf-8"))
        if blocks and isinstance(blocks[0], dict) and "kind" in blocks[0]:
            return norm(" ".join(b.get("text", "") for b in blocks))
        arr = [b for b in blocks if isinstance(b, dict)]
        return norm(" ".join(x.get("text", "") for x in arr))
    if ext in (".docx", ".pptx", ".xlsx", ".pdf", ".html", ".htm", ".rtf",
               ".srt", ".vtt", ".csv", ".tsv"):
        import extract_script
        blocks = extract_script.extract(path)
        return norm(" ".join(b.get("text", "") for b in blocks))
    return norm(io.open(path, encoding="utf-8", errors="replace").read())


def main(argv=None):
    ap = argparse.ArgumentParser(description="校验台词是否与源文件逐字一致")
    ap.add_argument("--source", required=True, help="原始剧本文件（任意支持格式）")
    ap.add_argument("--data", required=True, help="生成的 data.json")
    ap.add_argument("--limit", type=int, default=12, help="最多列出多少条不一致")
    ap.add_argument("--show-ok", action="store_true", help="同时列出通过的句子")
    a = ap.parse_args(argv)

    for p in (a.source, a.data):
        if not os.path.exists(p):
            print("找不到文件：%s" % p, file=sys.stderr)
            return 2
    try:
        src = load_source(a.source)
        data = json.load(io.open(a.data, encoding="utf-8"))
    except Exception as e:
        print("读取失败：%s" % e, file=sys.stderr)
        return 2
    if not src:
        print("源文件没抽到文字，无法比对。", file=sys.stderr)
        return 2

    bad, good = [], 0
    for sc in data.get("scenes", []):
        for it in sc.get("items", []):
            if it.get("k") != "L":
                continue
            t = norm(it.get("text"))
            if not t:
                continue
            if t in src:
                good += 1
                if a.show_ok:
                    print("  OK    [%s] %s" % (it.get("role"), t[:60]))
            else:
                bad.append((sc.get("name", ""), it.get("role", ""), it.get("text", "")))

    total = good + len(bad)
    print("台词 %d 句：逐字一致 %d 句" % (total, good))
    if not bad:
        print("\n通过：台词与源文件完全一致，一个字都没被改动。")
        return 0

    print("\n发现 %d 句与源文件对不上（可能被改写、或源文件本身是另一版）：" % len(bad))
    for i, (sc, role, txt) in enumerate(bad[:a.limit]):
        print("  %2d. [%s] %s" % (i + 1, role, txt[:80]))
        head = norm(txt)[:24]
        pos = src.find(head) if head else -1
        if pos >= 0:
            print("      源文件最接近的写法：…%s…" % src[pos:pos + 90])
    if len(bad) > a.limit:
        print("  …还有 %d 句" % (len(bad) - a.limit))
    print("\n失败：请把台词改回源文件的原文，或确认 --source 指对了文件。")
    return 1


if __name__ == "__main__":
    sys.exit(main())
