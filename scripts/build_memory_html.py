#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""build_memory_html.py -- inject a script-data JSON into template.html.

Usage:
    python build_memory_html.py data.json [-o index.html] [--template template.html]
                                          [--force] [--quiet]

The output is a single self-contained offline HTML page: the script data is
embedded as <script id="script-data" type="application/json">, so the page
needs no build step, no network, and no dependencies.

Exit codes: 0 ok, 1 validation error, 2 usage / IO error.
"""
from __future__ import annotations

import argparse
import io
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_TEMPLATE = os.path.join(os.path.dirname(HERE), "template.html")
DATA_OPEN = '<script id="script-data" type="application/json">'
DATA_CLOSE = "</script>"
APP_ANCHOR = '<script>\n"use strict";'

KEYS = ("B", "S", "A", "T", "L")


# --------------------------------------------------------------------------- #
# normalisation helpers (shared with validate_data.py)
# --------------------------------------------------------------------------- #
def derive_roles(data):
    seen = []
    for sc in data.get("scenes", []):
        for it in sc.get("items", []):
            if isinstance(it, dict) and it.get("k") == "L":
                r = (it.get("role") or "").strip()
                if r and r not in seen:
                    seen.append(r)
    return seen


def derive_beats(data):
    beats = []
    for sc in data.get("scenes", []):
        for it in sc.get("items", []):
            if isinstance(it, dict) and it.get("k") == "B":
                txt = (it.get("text") or "").strip()
                # "拍 1 · 独白背小抄" -> name="拍 1", title="独白背小抄"
                if "·" in txt:
                    name, title = txt.split("·", 1)
                else:
                    name, title = txt, ""
                beats.append({"name": name.strip(),
                              "title": title.strip(),
                              "key": (it.get("key") or "").strip()})
    return beats


def normalize(data):
    """Fill derived fields so the page always has a complete config."""
    data.setdefault("scenes", [])
    data.setdefault("title", "剧本")
    if not data.get("beats"):
        data["beats"] = derive_beats(data)
    if not data.get("roles"):
        data["roles"] = derive_roles(data)
    if not data.get("ensemble"):
        ens = [r for r in data["roles"] if "&" in r or "、" in r]
        data["ensemble"] = ens[0] if ens else ""
    if not data.get("stateKey"):
        slug = re.sub(r"[^0-9a-zA-Z]+", "_", data["title"]).strip("_").lower() or "script"
        data["stateKey"] = "script_memory_%s_v1" % slug[:40]
    if not data.get("myRoles"):
        sr = [r for r in data["roles"] if r != data["ensemble"]]
        data["myRoles"] = sr[:1] if len(sr) > 1 else sr
    return data


# --------------------------------------------------------------------------- #
# validation
# --------------------------------------------------------------------------- #
def validate(data):
    errs, warns = [], []
    if not isinstance(data, dict):
        return ["data.json 的顶层必须是一个 JSON 对象"], warns
    if not data.get("scenes"):
        errs.append("缺少 scenes（至少一场）")
    if not data.get("title"):
        warns.append("未提供 title，将使用「剧本」作为标题")

    roles = set(data.get("roles") or [])
    ens = data.get("ensemble") or ""
    if ens and ens not in roles:
        errs.append("ensemble=%r 不在 roles 里" % ens)

    n_line = n_beat = n_cue = 0
    for si, sc in enumerate(data.get("scenes", [])):
        if not isinstance(sc, dict):
            errs.append("scenes[%d] 不是对象" % si)
            continue
        if not sc.get("name"):
            warns.append("scenes[%d] 没有 name" % si)
        items = sc.get("items")
        if not isinstance(items, list) or not items:
            errs.append("scenes[%d]（%s）的 items 为空" % (si, sc.get("name", "")))
            continue
        for ii, it in enumerate(items):
            where = "scenes[%d].items[%d]" % (si, ii)
            if not isinstance(it, dict):
                errs.append("%s 不是对象" % where)
                continue
            k = it.get("k")
            if k not in KEYS:
                errs.append("%s 的 k=%r 非法（只能是 %s）" % (where, k, "/".join(KEYS)))
                continue
            text = it.get("text")
            if not isinstance(text, str) or not text.strip():
                errs.append("%s 的 text 为空" % where)
                continue
            if k == "L":
                n_line += 1
                r = (it.get("role") or "").strip()
                if not r:
                    errs.append("%s 是台词但没有 role" % where)
                elif roles and r not in roles:
                    warns.append("%s 的 role=%r 未在 roles 中声明" % (where, r))
                if r == ens and not ens:
                    errs.append("%s 用了齐诵标签但未声明 ensemble" % where)
            elif k == "B":
                n_beat += 1
            else:
                n_cue += 1
    if n_line == 0:
        errs.append("没有任何台词行（k=L）")
    if n_beat == 0:
        warns.append("没有任何段落标题（k=B），骨架卡片会是空的")
    if data.get("beats") and len(data["beats"]) != n_beat:
        warns.append("beats 有 %d 条，但正文里有 %d 个 k=B 段落标题"
                     % (len(data["beats"]), n_beat))
    if data.get("ensemble") and not any(
        isinstance(it, dict) and it.get("k") == "L" and it.get("role") == data["ensemble"]
        for sc in data.get("scenes", []) for it in sc.get("items", [])
    ):
        warns.append("声明了 ensemble=%r，但正文里没有齐诵台词" % data["ensemble"])
    return errs, warns


def stats(data):
    n_line = n_beat = 0
    n_mine = 0
    sr = [r for r in data.get("roles", []) if r != data.get("ensemble")]
    mine = set(data.get("myRoles") or [])
    for sc in data.get("scenes", []):
        for it in sc.get("items", []):
            if it.get("k") == "L":
                n_line += 1
                r = it.get("role")
                if r in mine or (r == data.get("ensemble") and mine):
                    n_mine += 1
            elif it.get("k") == "B":
                n_beat += 1
    return {"scenes": len(data.get("scenes", [])), "beats": n_beat,
            "lines": n_line, "mine": n_mine, "roles": len(sr)}


# --------------------------------------------------------------------------- #
# build
# --------------------------------------------------------------------------- #
def build(data, template_path, out_path):
    data = normalize(data)
    tpl = io.open(template_path, encoding="utf-8").read()
    if APP_ANCHOR not in tpl:
        raise RuntimeError("模板里找不到应用脚本入口，template.html 可能被改坏了")
    if DATA_OPEN in tpl:
        # rebuilding from an already-built file: drop the previous payload
        i = tpl.index(DATA_OPEN)
        j = tpl.index(DATA_CLOSE, i) + len(DATA_CLOSE)
        tpl = tpl[:i] + tpl[j:]

    payload = json.dumps(data, ensure_ascii=False, indent=2).replace("</", "<\\/")
    block = DATA_OPEN + "\n" + payload + "\n" + DATA_CLOSE + "\n"
    html = tpl.replace(APP_ANCHOR, block + APP_ANCHOR, 1)
    io.open(out_path, "w", encoding="utf-8", newline="").write(html)
    return html, data


def verify(html_path, expected):
    """Re-read the produced page and confirm the payload round-trips."""
    html = io.open(html_path, encoding="utf-8").read()
    i = html.index(DATA_OPEN) + len(DATA_OPEN)
    j = html.index(DATA_CLOSE, i)
    raw = html[i:j].strip().replace("<\\/", "</")
    got = json.loads(raw)
    if got != expected:
        raise RuntimeError("注入后的数据与源 data.json 不一致")
    if html.count(DATA_OPEN) != 1:
        raise RuntimeError("script-data 块出现了 %d 次" % html.count(DATA_OPEN))
    if "</script>" not in html[j:]:
        raise RuntimeError("script-data 块没有被正确闭合")
    return got


def main(argv=None):
    ap = argparse.ArgumentParser(description="把剧本数据注入模板，生成离线记忆训练页")
    ap.add_argument("data", help="data.json 路径")
    ap.add_argument("-o", "--out", default=None, help="输出 html 路径（默认 ./index.html）")
    ap.add_argument("--template", default=DEFAULT_TEMPLATE, help="模板路径")
    ap.add_argument("--force", action="store_true", help="校验有报错时仍然生成")
    ap.add_argument("--quiet", action="store_true")
    a = ap.parse_args(argv)

    try:
        data = json.load(io.open(a.data, encoding="utf-8"))
    except Exception as e:
        print("读不了 data.json：%s" % e, file=sys.stderr)
        return 2

    errs, warns = validate(data)
    for w in warns:
        print("WARN  " + w, file=sys.stderr)
    if errs:
        for e in errs:
            print("ERROR " + e, file=sys.stderr)
        if not a.force:
            print("\n校验未通过，已中止（确认无误可加 --force）", file=sys.stderr)
            return 1

    if not os.path.exists(a.template):
        print("找不到模板：%s" % a.template, file=sys.stderr)
        return 2
    out = a.out or os.path.join(os.getcwd(), "index.html")
    try:
        html, data = build(data, a.template, out)
        verify(out, data)
    except Exception as e:
        print("生成失败：%s" % e, file=sys.stderr)
        return 2

    if not a.quiet:
        s = stats(data)
        print("已生成：%s" % out)
        print("  标题    %s" % data["title"])
        print("  结构    %d 场 / %d 段骨架 / %d 句台词（我的 %d 句）"
              % (s["scenes"], s["beats"], s["lines"], s["mine"]))
        print("  角色    %s%s" % ("、".join(data["roles"]),
                                  "（齐诵 %s）" % data["ensemble"] if data["ensemble"] else ""))
        print("  体积    %.1f KB" % (len(html.encode("utf-8")) / 1024.0))
    return 0


if __name__ == "__main__":
    sys.exit(main())
