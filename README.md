# script-memory-skill

把任意格式的剧本 / 讲稿，变成一份**能真正拿来背**的离线训练页。

> Turn a theatre script, dialogue, or speech draft into a single-file offline
> memorisation trainer — without changing one word of dialogue.

## 它解决什么

拿到一份剧本，你要背自己的词。市面上的做法无非两种：打印出来反复读，或者录一遍当音频循环。两种都低效——前者不知道哪儿卡，后者只能整体听。

这个 skill 把流程拆成有顺序的四步，并做成一个网页：

1. **骨架** —— 先记 6-10 个画面，不记词。忘词时想「现在第几拍、画面是什么」，词自己会跟着流出来。
2. **锚点** —— 只背每句开头两三个词。长句记不住是因为在背「一整句」，而人脑接话靠的是开头。
3. **零件** —— 把重复句式（`and you? ×2`、`go straight / turn left ×3`）拎出来单练，背一句白送两三句。
4. **小抄** —— 一键生成「每句头三个词 + 段号」，抄到纸上当合法提词器。

配套的第二个产出是**统一后的剧本文档**：编号、角色标签、动作/提示标记全部规范化，但**台词一个字都不动**，并且由脚本强制证明这一点。

## 安装

把本仓库放进你的 skill 目录：

```bash
# WorkBuddy / 通用
git clone https://github.com/yzh5310/script-memory-skill.git ~/.workbuddy/skills/script-memory
```

也可以直接把整个目录复制到 `~/.workbuddy/skills/script-memory/`。仓库根就是 skill 根，`SKILL.md` 在顶层，不需要额外打包。

## 依赖

只跑抽取和生成，**零第三方依赖**（Python 3.8+ 标准库 + Node 可选）。

| 用途 | 依赖 |
|---|---|
| docx / pptx / xlsx / txt / md / html / csv / srt | 无 |
| pdf | `pypdf` 或 `PyPDF2`，或系统装了 `pdftotext` |
| 无头冒烟测试 | Node.js（可选，不装也能用） |

要补 PDF 依赖时请装进隔离环境，别装全局：

```bash
python -m venv .venv && .venv/bin/pip install pypdf
# Windows: python -m venv .venv; .venv\Scripts\pip install pypdf
```

## 三分钟跑通

```bash
S=~/.workbuddy/skills/script-memory

# 1. 抽取（支持 docx / txt / md / pdf / pptx / xlsx / html / srt …）
python $S/scripts/extract_script.py "剧本.docx" -o work/

# 2. 按 work/剧本.txt 的内容，写一份 data.json（结构见 schemas/script-data.schema.json）
#    也可以直接从示例改起：
cp $S/examples/mini-dialogue.data.json work/data.json

# 3. 生成 + 校验 + 冒烟
python $S/scripts/build_memory_html.py work/data.json -o work/index.html
python $S/scripts/validate_data.py      work/data.json --html work/index.html
python $S/scripts/check_fidelity.py     --source "剧本.docx" --data work/data.json
node   $S/scripts/smoke_boot.js         work/index.html
```

打开 `work/index.html` 即可用。文件是自包含的，拷到手机、U 盘、离线电脑都能跑。

## data.json 长什么样

```json
{
  "title": "Brave to Speak",
  "subtitle": "勇敢开麦",
  "roles": ["A", "B", "A & B"],
  "ensemble": "A & B",
  "beatUnit": "拍",
  "keyParts": ["and you? ×2", "cheat sheet ×4"],
  "rescueLines": ["\"My brain is sweating!\"", "把话头递给对手：\"Wait — what are you hiding?\""],
  "scenes": [
    {
      "name": "第 1 场 · 开场",
      "items": [
        { "k": "S", "text": "A、B 并排走到台前，面向观众。" },
        { "k": "B", "text": "拍 1 · 独白背小抄" },
        { "k": "L", "role": "A", "text": "Good afternoon, everyone!", "zh": "各位下午好！" },
        { "k": "A", "text": "说到 how to respond 时定住两秒。" },
        { "k": "T", "text": "词与词之间要有停顿，等观众反应。" }
      ]
    }
  ]
}
```

| `k` | 含义 |
|---|---|
| `B` | 骨架段标题 |
| `S` | 场景 |
| `A` | 动作 / 走位 |
| `T` | 提示（语气、节奏、停顿） |
| `L` | 台词（**必须与源文件逐字一致**） |

`roles` / `beats` / `stateKey` / `myRoles` 都可以省略，会自动推导。只填 `title` + `scenes` 也能出页面。

## 页面里有什么

| 区块 | 作用 |
|---|---|
| 🎭 我的角色 | 多选。绿色＝你的词，停下等你脱稿；橙色＝对方的词，自动播放 |
| ② 骨架速记 | 点任意一段直接跳到该段第一句 |
| ③ 顺序练习 | 自动念对方 → 轮到你就模糊遮罩 → 卡壳点「💡 看锚点」只露前两个词 |
| ④ 锚点训练 | 只列你要背的句子，红色加粗是锚点，其余先遮住 |
| ⑤ 全篇一览 | 点任意一句直接播放 |
| 📝 生成小抄 | 复制「每句头三个词 + 段号」到道具纸 |
| 📋 复制说明 | 把使用说明 + 记忆法发到剧组群 |

快捷键：`空格` 播放/暂停 · `←` `→` 上一句/下一句 · `Enter` 我说完了 · `L` 循环本句 · `Esc` 停止。
进度存在 localStorage，刷新不丢。

单人讲稿（演讲、独白）会自动降级：传一个角色（如 `"Speaker"`）即可，页面隐藏「对方台词」面板。

## 质量闸门

三条命令，缺一不可：

| 命令 | 拦住的错误 |
|---|---|
| `validate_data.py` | 结构错误、k 值非法、角色没声明、空台词；顺带扫出「疑似把小写 L 打成大写 I」「`dosen't`」「异常连续空格」等疑点 |
| `check_fidelity.py` | **台词被改写**。每句台词必须在源文件里找到逐字对应，否则非零退出 |
| `smoke_boot.js` | 页面启动即报错（脚本抛异常但 HTML 看起来正常）。用桩 DOM 无头启动，断言每个区块真的渲染出来了 |

`check_fidelity.py` 是这套工具的核心价值：它把「我保证没改台词」变成可执行的证明。只做空白归一和引号/破折号折合，不做拼写容错——所以模型「顺手把台词改通顺」这类事故一定能被抓到。

## 目录

```
script-memory/
├── SKILL.md                        # 工作流主文档
├── template.html                   # 页面模板（数据注入其中，不要手改数据）
├── schemas/script-data.schema.json # data.json 的规范结构
├── references/
│   ├── extraction.md               # 各格式抽取要点与排查顺序
│   ├── normalization.md            # 统一剧本：改什么、绝不改什么
│   └── memory-methods.md           # 每块设计背后的记忆法
├── examples/
│   ├── mini-dialogue.data.json     # 双人短剧示例
│   └── mini-monologue.data.json    # 单人演讲示例
└── scripts/
    ├── extract_script.py
    ├── build_memory_html.py
    ├── validate_data.py
    ├── check_fidelity.py
    └── smoke_boot.js
```

## 边界

不适用：翻译、改写剧本、评分、判断表演好坏、替你写台词。

`template.html` 是数据驱动的：换剧本只改 `data.json`，不要改模板；要改交互或样式时才动模板。
模板改完务必重跑 `smoke_boot.js`。

## License

MIT
