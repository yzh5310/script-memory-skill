#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""validate_data.py -- check a script data.json before / after building.

    python validate_data.py data.json
    python validate_data.py data.json --html index.html     # 同时校验产物

Exit codes: 0 ok (warnings allowed), 1 errors found, 2 usage / IO error.
"""
from __future__ import annotations

import argparse
import io
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from build_memory_html import DATA_CLOSE, DATA_OPEN, normalize, stats, validate  # noqa: E402

EXTRA_CHECKS = (
    (re.compile(r"[“”]\s*[“”]"), "空的双引号对，可能是排版残留"),
    (re.compile(r"\bl\s+am\b"), "疑似把小写 L 打成了大写 I（如 “l am” → “I am”）"),
    (re.compile(r"\bdosen'?t\b", re.I), "拼写疑似应为 “doesn't”"),
    (re.compile(r"\s{3,}"), "台词里有三个以上连续空格，确认是有意停顿还是排版噪音"),
    (re.compile(r"[\u3000]"), "台词里出现全角空格，英文台词建议换成半角"),
)


def lint(data):
    notes = []
    for sc in data.get("scenes", []):
        for it in sc.get("items", []):
            if it.get("k") != "L":
                continue
            t = it.get("text", "")
            for rx, msg in EXTRA_CHECKS:
                if rx.search(t):
                    notes.append("[%s] %s｜%s" % (it.get("role", "?"), msg, t[:48]))
    return notes


def check_html(path, data):
    errs = []
    if not os.path.exists(path):
        return ["找不到产物 %s" % path]
    html = io.open(path, encoding="utf-8").read()
    if html.count(DATA_OPEN) != 1:
        errs.append("script-data 块出现 %d 次（应为 1）" % html.count(DATA_OPEN))
    if "id=\"script-data\"" not in html:
        errs.append("产物里没有 script-data 块，页面会读不到剧本")
    if "__SCRIPT_DATA__" in html or "%%" in html.split("script-data")[0][:2000]:
        errs.append("产物里仍留有未替换的占位符")
    try:
        i = html.index(DATA_OPEN) + len(DATA_OPEN)
        j = html.index(DATA_CLOSE, i)
        got = json.loads(html[i:j].strip().replace("<\\/", "</"))
        if got != normalize(dict(data)):
            errs.append("产物里的数据与 data.json 不一致")
    except Exception as e:
        errs.append("无法从产物里读回数据：%s" % e)
    if "<script>" not in html or html.rstrip().endswith("</html>") is False:
        errs.append("产物 HTML 结构不完整")
    return errs


def main(argv=None):
    ap = argparse.ArgumentParser(description="校验剧本数据与生成产物")
    ap.add_argument("data")
    ap.add_argument("--html", default=None, help="顺带校验已生成的 index.html")
    ap.add_argument("--strict", action="store_true", help="把警告也当成失败")
    a = ap.parse_args(argv)

    try:
        data = json.load(io.open(a.data, encoding="utf-8"))
    except Exception as e:
        print("读不了 %s：%s" % (a.data, e), file=sys.stderr)
        return 2

    errs, warns = validate(data)
    notes = lint(data)
    if a.html:
        errs = errs + check_html(a.html, data)

    d = normalize(json.loads(json.dumps(data)))
    s = stats(d)

    print("== 结构 ==")
    print("标题    %s" % d["title"])
    print("角色    %s%s" % ("、".join(d["roles"]) or "（未声明）",
                            "　齐诵 %s" % d["ensemble"] if d["ensemble"] else ""))
    print("规模    %d 场 / %d 段骨架 / %d 句台词（我的 %d 句）"
          % (s["scenes"], s["beats"], s["lines"], s["mine"]))
    print("我的角色 %s" % ("、".join(d["myRoles"]) or "（未设置）"))
    print("存储键  %s" % d["stateKey"])

    if notes:
        print("\n== 台词疑点（不动原文，仅提示）==")
        for x in notes:
            print("  · " + x)
    if warns:
        print("\n== 警告 ==")
        for w in warns:
            print("  · " + w)
    if errs:
        print("\n== 错误 ==")
        for e in errs:
            print("  · " + e)
        return 1

    print("\n通过：可以生成 HTML。")
    if a.strict and warns:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
