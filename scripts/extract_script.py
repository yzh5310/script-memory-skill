#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""extract_script.py -- pull a script out of a file, whatever format it is in.

    python extract_script.py <file> [-o outdir] [--json-only]

Writes two files next to the input (or into -o):

    <name>.txt          plain text, one paragraph per line (dialogue stays intact)
    <name>.blocks.json  full fidelity: per-paragraph style / bold / italic / runs

Supported: .docx .doc .txt .md .csv .tsv .json .html .pdf .pptx .xlsx .srt .vtt .rtf .odt
Only the standard library is required for Office / text / html formats; PDF needs
pypdf (or PyPDF2, or a `pdftotext` binary on PATH).
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import os
import re
import shutil
import subprocess
import sys
import zipfile
from xml.etree import ElementTree as ET

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
TEXT_ENC = ("utf-8-sig", "utf-8", "gb18030", "big5", "cp1252", "latin-1")


# --------------------------------------------------------------------------- #
def _blocks_to_text(blocks):
    out = []
    for b in blocks:
        if b["kind"] == "empty":
            out.append("")
        else:
            out.append(b["text"])
    return "\n".join(out) + "\n"


def _mk(kind, text, style="", bold=False, italic=False, runs=None):
    b = {"kind": kind, "text": text, "style": style, "bold": bold, "italic": italic}
    if runs:
        b["runs"] = runs
    return b


# --------------------------------------------------------------------------- #
# DOCX
# --------------------------------------------------------------------------- #
def read_docx(path):
    with zipfile.ZipFile(path) as z:
        xml = z.read("word/document.xml").decode("utf-8", "replace")
    root = ET.fromstring(xml)
    body = root.find(W + "body")
    blocks = []
    if body is None:
        return blocks

    def para(el):
        style = ""
        ppr = el.find(W + "pPr")
        if ppr is not None:
            ps = ppr.find(W + "pStyle")
            if ps is not None:
                style = ps.get(W + "val") or ""
        runs, text = [], ""
        for r in el.iter(W + "r"):
            rpr = r.find(W + "rPr")
            b = rpr is not None and rpr.find(W + "b") is not None
            i = rpr is not None and rpr.find(W + "i") is not None
            t = "".join(n.text or "" for n in r.iter(W + "t"))
            br = r.find(W + "br")
            if br is not None and not t:
                t = " "
            if not t:
                continue
            text += t
            runs.append({"t": t, "b": b, "i": i})
        # merge neighbouring runs with the same flags
        merged = []
        for r in runs:
            if merged and merged[-1]["b"] == r["b"] and merged[-1]["i"] == r["i"]:
                merged[-1]["t"] += r["t"]
            else:
                merged.append(dict(r))
        kinds = set((r["b"], r["i"]) for r in merged if r["t"].strip())
        b_all = kinds == {(True, False)} or kinds == {(True, True)}
        i_all = kinds == {(False, True)} or kinds == {(True, True)}
        mixed = len(kinds) > 1
        return _mk("p", text, style, b_all, i_all, merged if mixed else None)

    def table(el):
        rows = []
        for tr in el.findall(W + "tr"):
            cells = []
            for tc in tr.findall(W + "tc"):
                cells.append(" ".join(
                    "".join(n.text or "" for n in p.iter(W + "t"))
                    for p in tc.findall(W + "p")).strip())
            rows.append(cells)
        return {"kind": "table", "rows": rows,
                "text": "\n".join(" | ".join(r) for r in rows),
                "style": "", "bold": False, "italic": False}

    for el in body:
        tag = el.tag.split("}")[-1]
        if tag == "p":
            b = para(el)
            if b["text"].strip():
                blocks.append(b)
            else:
                blocks.append(_mk("empty", ""))
        elif tag == "tbl":
            blocks.append(table(el))
    return blocks


# --------------------------------------------------------------------------- #
# PPTX
# --------------------------------------------------------------------------- #
def read_pptx(path):
    A = "{http://schemas.openxmlformats.org/drawingml/2006/main}"
    blocks = []
    with zipfile.ZipFile(path) as z:
        names = [n for n in z.namelist()
                 if re.match(r"ppt/slides/slide\d+\.xml$", n)]
        names.sort(key=lambda n: int(re.findall(r"\d+", n)[-1]))
        for n in names:
            root = ET.fromstring(z.read(n).decode("utf-8", "replace"))
            blocks.append(_mk("p", "── %s ──" % os.path.basename(n), style="slide"))
            for sp in root.iter(A + "p"):
                txt = "".join(t.text or "" for t in sp.iter(A + "t")).strip()
                if txt:
                    blocks.append(_mk("p", txt))
    return blocks


# --------------------------------------------------------------------------- #
# XLSX / CSV / TSV
# --------------------------------------------------------------------------- #
def read_xlsx(path):
    with zipfile.ZipFile(path) as z:
        shared = []
        if "xl/sharedStrings.xml" in z.namelist():
            sroot = ET.fromstring(z.read("xl/sharedStrings.xml").decode("utf-8", "replace"))
            for si in sroot:
                shared.append("".join(t.text or "" for t in si.iter(
                    "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}t")))
        S = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
        blocks = []
        sheets = sorted(n for n in z.namelist() if re.match(r"xl/worksheets/sheet\d+\.xml$", n))
        for n in sheets:
            root = ET.fromstring(z.read(n).decode("utf-8", "replace"))
            blocks.append(_mk("p", "── %s ──" % os.path.basename(n), style="sheet"))
            for row in root.iter(S + "row"):
                cells = []
                for c in row.findall(S + "c"):
                    v = c.find(S + "v")
                    val = "" if v is None else (v.text or "")
                    if c.get("t") == "s" and val.isdigit():
                        val = shared[int(val)] if int(val) < len(shared) else val
                    if c.get("t") == "inlineStr":
                        val = "".join(t.text or "" for t in c.iter(S + "t"))
                    cells.append(val)
                if any(x.strip() for x in cells):
                    blocks.append(_mk("p", " | ".join(cells)))
    return blocks


def read_delim(path, delim=None):
    raw = read_text(path)
    if delim is None:
        first = raw.splitlines()[0] if raw.splitlines() else ""
        delim = "\t" if first.count("\t") > first.count(",") else ","
    rows = list(csv.reader(io.StringIO(raw), delimiter=delim))
    blocks = []
    for r in rows:
        cells = [c.strip().replace("\r", " ").replace("\n", " ") for c in r]
        if any(cells):
            blocks.append(_mk("p", " | ".join(cells)))
    return blocks


# --------------------------------------------------------------------------- #
# HTML / PDF / RTF / text
# --------------------------------------------------------------------------- #
def read_html(path):
    raw = read_text(path)
    raw = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", raw)
    raw = re.sub(r"(?i)</(p|div|li|tr|h[1-6]|br)\s*>", "\n", raw)
    raw = re.sub(r"(?i)<br\s*/?>", "\n", raw)
    raw = re.sub(r"(?s)<[^>]+>", " ", raw)
    raw = (raw.replace("&nbsp;", " ").replace("&amp;", "&")
              .replace("&lt;", "<").replace("&gt;", ">").replace("&quot;", '"'))
    return [_mk("p", ln.strip()) for ln in raw.splitlines() if ln.strip()]


def read_pdf(path):
    try:
        import pypdf  # noqa
        reader = pypdf.PdfReader(path)
        pages = [(p.extract_text() or "") for p in reader.pages]
    except Exception:
        try:
            import PyPDF2  # noqa
            reader = PyPDF2.PdfReader(path)
            pages = [(p.extract_text() or "") for p in reader.pages]
        except Exception:
            exe = shutil.which("pdftotext")
            if not exe:
                raise RuntimeError(
                    "PDF 需要 pypdf / PyPDF2，或系统里有 pdftotext。"
                    "可先转成 docx/txt 再喂给我。")
            out = subprocess.run([exe, "-layout", path, "-"],
                                 capture_output=True)
            pages = [out.stdout.decode("utf-8", "replace")]
    blocks = []
    for i, pg in enumerate(pages):
        if len(pages) > 1:
            blocks.append(_mk("p", "── page %d ──" % (i + 1), style="page"))
        for ln in pg.splitlines():
            if ln.strip():
                blocks.append(_mk("p", ln.strip()))
    return blocks


def read_rtf(path):
    raw = read_text(path)
    body = raw[raw.find("\\", 3):] if raw.lstrip().startswith("{\\rtf") else raw
    body = re.sub(r"\\'([0-9a-fA-F]{2})",
                  lambda m: bytes([int(m.group(1), 16)]).decode("cp1252", "replace"), body)
    body = re.sub(r"\\par[d]?", "\n", body)
    body = re.sub(r"\\[a-zA-Z]+-?\d* ?", "", body)
    body = body.replace("{", "").replace("}", "")
    return [_mk("p", ln.strip()) for ln in body.splitlines() if ln.strip()]


def read_subs(path):
    raw = read_text(path)
    blocks = []
    for block in re.split(r"\n\s*\n", raw):
        lines = [l.strip() for l in block.splitlines() if l.strip()]
        if not lines:
            continue
        if re.match(r"^\d+$", lines[0]):
            lines = lines[1:]
        lines = [l for l in lines if "-->" not in l]
        if lines:
            blocks.append(_mk("p", " ".join(lines)))
    return blocks


def read_text(path):
    data = io.open(path, "rb").read()
    for enc in TEXT_ENC:
        try:
            return data.decode(enc)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", "replace")


def read_plain(path):
    lines = read_text(path).splitlines()
    return [_mk("p", ln) if ln.strip() else _mk("empty", "") for ln in lines]


def read_json_file(path):
    try:
        obj = json.loads(read_text(path))
    except Exception:
        return read_plain(path)
    lines = []

    def walk(o):
        if isinstance(o, dict):
            if "text" in o and isinstance(o["text"], str):
                lines.append(o["text"])
                return
            for v in o.values():
                walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)
        elif isinstance(o, str):
            lines.append(o)
    walk(obj)
    return [_mk("p", l) for l in lines if l.strip()]


# --------------------------------------------------------------------------- #
READERS = {
    ".docx": read_docx,
    ".pptx": read_pptx,
    ".xlsx": read_xlsx,
    ".csv": read_delim,
    ".tsv": read_delim,
    ".html": read_html,
    ".htm": read_html,
    ".pdf": read_pdf,
    ".rtf": read_rtf,
    ".srt": read_subs,
    ".vtt": read_subs,
    ".json": read_json_file,
    ".txt": read_plain,
    ".md": read_plain,
    ".markdown": read_plain,
    ".text": read_plain,
}

HINTS = {
    ".doc": "旧版 .doc 读不了：先用 Word/WPS「另存为 .docx」再试，或复制粘贴成 .txt。",
    ".odt": "旧版 .odt 读不了：先另存为 .docx 或 .txt。",
    ".pages": "Apple Pages 读不了：先导出为 .docx 或 .pdf。",
    ".wps": "WPS 专有格式读不了：先另存为 .docx。",
}


def extract(path):
    ext = os.path.splitext(path)[1].lower()
    if ext in READERS:
        return READERS[ext](path)
    if ext in HINTS:
        raise RuntimeError(HINTS[ext])
    # unknown extension: sniff
    head = io.open(path, "rb").read(8)
    if head[:2] == b"PK":
        try:
            with zipfile.ZipFile(path) as z:
                names = z.namelist()
            if any(n.startswith("word/") for n in names):
                return read_docx(path)
            if any(n.startswith("ppt/") for n in names):
                return read_pptx(path)
            if any(n.startswith("xl/") for n in names):
                return read_xlsx(path)
        except Exception:
            pass
    if head[:4] == b"%PDF":
        return read_pdf(path)
    return read_plain(path)


def main(argv=None):
    ap = argparse.ArgumentParser(description="从任意格式的剧本文件里抽取文本")
    ap.add_argument("path")
    ap.add_argument("-o", "--outdir", default=None)
    ap.add_argument("--json-only", action="store_true")
    ap.add_argument("--quiet", action="store_true")
    a = ap.parse_args(argv)

    if not os.path.exists(a.path):
        print("找不到文件：%s" % a.path, file=sys.stderr)
        return 2
    try:
        blocks = extract(a.path)
    except Exception as e:
        print("抽取失败：%s" % e, file=sys.stderr)
        return 1
    if not blocks:
        print("没有抽到任何文字，请确认文件内容。", file=sys.stderr)
        return 1

    outdir = a.outdir or os.path.dirname(os.path.abspath(a.path))
    if outdir and not os.path.isdir(outdir):
        os.makedirs(outdir, exist_ok=True)
    stem = os.path.splitext(os.path.basename(a.path))[0]
    txt_path = os.path.join(outdir, stem + ".txt")
    json_path = os.path.join(outdir, stem + ".blocks.json")

    text = _blocks_to_text(blocks)
    io.open(json_path, "w", encoding="utf-8", newline="").write(
        json.dumps(blocks, ensure_ascii=False, indent=1))
    if not a.json_only:
        io.open(txt_path, "w", encoding="utf-8", newline="").write(text)

    if not a.quiet:
        n_p = sum(1 for b in blocks if b["kind"] == "p")
        n_t = sum(1 for b in blocks if b["kind"] == "table")
        n_b = sum(1 for b in blocks if b.get("bold"))
        n_i = sum(1 for b in blocks if b.get("italic"))
        n_s = sum(1 for b in blocks if b.get("style"))
        print("来源    %s" % a.path)
        print("段落    %d 段 + %d 张表" % (n_p, n_t))
        print("格式线索 加粗 %d 段 / 斜体 %d 段 / 带样式 %d 段" % (n_b, n_i, n_s))
        if not a.json_only:
            print("纯文本  %s" % txt_path)
        print("结构    %s" % json_path)
        styles = sorted(set(b.get("style") for b in blocks if b.get("style")))
        if styles:
            print("样式名  %s" % "、".join(styles[:12]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
