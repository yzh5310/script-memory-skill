#!/usr/bin/env node
/**
 * smoke_boot.js -- headless boot test for a generated memorisation page.
 *
 *   node smoke_boot.js index.html                    # 单页冒烟
 *   node smoke_boot.js generated.html reference.html # 额外逐句比对（回归用）
 *
 * Uses a stub DOM, so no browser or jsdom install is needed. Exits non-zero on
 * any failure. Run this before delivering the page.
 */
"use strict";
const fs = require("fs");
const vm = require("vm");

function mkEl(id) {
  const el = {
    id, children: [], textContent: "", innerHTML: "", style: {}, dataset: {},
    classList: {
      _s: new Set(),
      add(...c) { c.forEach(x => this._s.add(x)); },
      remove(...c) { c.forEach(x => this._s.delete(x)); },
      toggle(c, f) { (f === undefined ? !this._s.has(c) : f) ? this._s.add(c) : this._s.delete(c); },
      contains(c) { return this._s.has(c); }
    },
    getAttribute(k) { return (this.attrs || {})[k] === undefined ? null : this.attrs[k]; },
    setAttribute(k, v) { (this.attrs = this.attrs || {})[k] = String(v); },
    appendChild(c) { this.children.push(c); return c; },
    remove() {}, querySelector() { return null; }, querySelectorAll() { return []; },
    scrollIntoView() {}, select() {},
    click() { if (typeof this.onclick === "function") this.onclick({ target: this, currentTarget: this }); }
  };
  Object.defineProperty(el, "parentNode", { get() { return mkEl(id + ":parent"); } });
  return el;
}

const KEYS = ["LINES", "ALL", "BEATS", "ROLES", "ENS", "meRoles", "voiceNames", "SCENES", "isMine", "CFG"];

function boot(file) {
  const html = fs.readFileSync(file, "utf8");
  const els = {};
  const db = /<script id="script-data" type="application\/json">([\s\S]*?)<\/script>/.exec(html);
  // pages built by this skill embed the data; legacy hand-written pages carry it inline
  if (db) {
    els["script-data"] = Object.assign(mkEl("script-data"), { textContent: db[1].replace(/<\\\//g, "</") });
  }
  const m = /\n<script>\n"use strict";([\s\S]*?)\n<\/script>/.exec(html);
  if (!m) throw new Error("没有找到应用脚本：" + file);

  const store = {};
  const ctx = {
    console,
    document: {
      title: "", body: mkEl("body"),
      getElementById: id => (els[id] = els[id] || mkEl(id)),
      querySelectorAll: () => [], querySelector: () => null,
      createElement: t => mkEl("new:" + t), addEventListener: () => {}
    },
    localStorage: {
      getItem: k => (k in store ? store[k] : null),
      setItem: (k, v) => { store[k] = String(v); },
      removeItem: k => { delete store[k]; }
    },
    navigator: { clipboard: { writeText: () => Promise.resolve() } },
    setTimeout: () => 0,
    speechSynthesis: {
      getVoices: () => [{ name: "V1", lang: "en-US" }, { name: "V2", lang: "en-GB" }, { name: "V3", lang: "en-US" }],
      cancel: () => {}, speak: () => {}, onvoiceschanged: null
    },
    SpeechSynthesisUtterance: function (t) { this.text = t; }
  };
  ctx.window = ctx; ctx.globalThis = ctx;
  vm.createContext(ctx);
  vm.runInContext(m[1], ctx, { filename: file });
  const out = { _els: els, _get: id => els[id] };
  KEYS.forEach(k => { out[k] = ctx[k]; });
  return out;
}

let fail = 0;
const ok = (c, msg) => { console.log((c ? "  PASS  " : "  FAIL  ") + msg); if (!c) fail++; };
const html = h => (h || "");

const gen = boot(process.argv[2]);
const isMine = typeof gen.isMine === "function"
  ? l => gen.isMine(l.role)
  : l => gen.meRoles.indexOf(l.role) >= 0;
const mine = gen.LINES.filter(isMine).length;

console.log("== " + process.argv[2] + " ==");
ok(gen.LINES.length > 0, "台词句数 " + gen.LINES.length);
ok(gen.BEATS.length > 0, "骨架卡片 " + gen.BEATS.length + " 段");
ok(gen.ROLES.length > 0, "角色 " + gen.ROLES.join(" / ") + (gen.ENS ? "（齐诵 " + gen.ENS + "）" : ""));
ok(gen.meRoles.length > 0, "默认「我」= " + gen.meRoles.join("、") + "（" + mine + " 句）");
ok(html(gen._get("beatsWrap").innerHTML).split("data-beat=").length - 1 === gen.BEATS.length, "骨架卡片渲染数一致");
ok(html(gen._get("meChips").innerHTML).length > 0, "角色选择器已渲染");
ok(html(gen._get("anchorWrap").innerHTML).split("anchor-card").length - 1 === mine, "锚点区句数与我的台词一致");
ok(html(gen._get("scriptWrap").innerHTML).split("data-line=").length - 1 === gen.LINES.length, "全篇一览句数一致");
ok(html(gen._get("helpBody").innerHTML).indexOf("记忆法") >= 0, "帮助卡已渲染");
ok(html(gen._get("h1en").textContent).length > 0, "页头标题 = " + gen._get("h1en").textContent);
ok(html(gen._get("voiceRow").innerHTML).split("<select").length - 1 === gen.ROLES.filter(r => r !== gen.ENS).length,
   "每个单人角色一个音色选择器");
const hiddenPartner = gen._els["partnerCard"] !== undefined && gen._els["partnerCard"].style.display === "none";
ok(gen.ENS !== "" || hiddenPartner, "单人稿正确隐藏「对方台词」卡");
if (!mine) console.log("  INFO  我的角色没有匹配任何台词，请检查 roles / myRoles");

if (process.argv[3]) {
  const ref = boot(process.argv[3]);
  const key = f => gen.LINES.map(f).join("\u0001") === ref.LINES.map(f).join("\u0001");
  console.log("== 与参考页比对 ==");
  ok(gen.LINES.length === ref.LINES.length, "句数 " + gen.LINES.length + " == " + ref.LINES.length);
  ok(key(l => l.text), "每句台词正文逐字一致");
  ok(key(l => l.role), "角色归属一致");
  ok(key(l => l.zh || ""), "中文大意一致");
  ok(key(l => (l.cues || []).map(c => c.k + c.text).join("~")), "场景/动作/提示挂载一致");
  ok(key(l => String(l.beatIdx)), "段落索引一致");
  ok(gen.ROLES.join("|") === ref.ROLES.join("|"), "角色表一致");
}

console.log(fail ? "\n失败 " + fail + " 项" : "\n全部通过");
process.exit(fail ? 1 : 0);
