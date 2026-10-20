# Fizgig 汉化补丁（简体中文）

把 [Fizgig](https://github.com/shootthesound/Fizgig) 的网页界面（Web UI）改成简体中文。
**只改界面文字，不动任何功能、配置或数据。**

> **⚠️ 翻译由 AI 完成**
> 本补丁的全部 1140 条译文由 AI（Claude / DeepSeek 等大模型）根据
> `TRANSLATE_RULES.md` 中的规则批量翻译，**未经母语者逐条校对**。
> 个别用词可能不够地道。请当作「机器翻译 + 人工可用」来对待：
> 觉得哪里别扭，直接改 `dictionary.json` 里那一条，再重新安装即可，
> 不需要重译全部。发现明显错译，欢迎提 issue 或 PR。

---

## 一分钟上手

### 放在哪？

**推荐：放在 Fizgig 根目录里，名字叫 `zh_patch`：**

```
<Fizgig 根目录>\              ← 里面有 fizgig.py
├── venv\
├── src\
├── user_data\
└── zh_patch\                 ← 把本文件夹放这里
    ├── 一键汉化.bat
    ├── install.py
    └── dictionary.json
```

放这里的好处：脚本会自动认出自己的上一级就是 Fizgig，不用写任何配置；
`一键汉化.bat` 也能直接找到 `..\venv\Scripts\python.exe`。

**放在别的地方也行**，只要告诉它 Fizgig 在哪。三选一：

| 方式 | 怎么做 |
|---|---|
| 配置文件 | 在本文件夹里建一个 `fizgig_root.txt`，里面写 Fizgig 根目录路径 |
| 环境变量 | 设 `FIZGIG_ROOT` 环境变量指向 Fizgig 根目录 |
| 就近放 | 放在 Fizgig 根目录的下一层（如上面的 `zh_patch\`） |

判断 Fizgig 根目录的标准：目录里**同时有** `fizgig.py` 和 `src/fizgig/web/static/`。

### 然后

**双击 `一键汉化.bat`** 就行：

| 你现在的界面 | 双击之后 |
|---|---|
| 英文 | 变成中文 |
| 中文 | 变回英文 |

改完请**重启 Fizgig**（或浏览器里按 `Ctrl+F5` 强刷）才会看到效果。

也可以用命令行（把 `$PATCH` 换成本文件夹的实际路径）：

```powershell
$PATCH = '<本文件夹的路径>'
$PY    = '<Fizgig 根目录>\venv\Scripts\python.exe'

# 安装汉化
& $PY "$PATCH\install.py" install

# 卸载，还原英文
& $PY "$PATCH\install.py" uninstall

# 看当前状态
& $PY "$PATCH\install.py" status

# 只做体检，不改任何文件
& $PY "$PATCH\install.py" check
```

> `venv\Scripts\python.exe` 是 Fizgig 自己的 Python。如果你的 Fizgig 装在别的
> 目录，把 `$PY` 换成你自己的即可。

---

## 它到底改了什么

只有三个文件：

```
src/fizgig/web/static/index.html
src/fizgig/web/static/app.js
src/fizgig/web/static/style.css
```

**没有碰**：你的 `prefs.json`、`user_data/`（模型、LoRA、预设、缓存）、
`output_loras/`、训练数据、任何 Python 后端代码、任何配置。

安装前会把原件复制到 `backup/<时间戳>/`，卸载时原样写回。

---

## 安全性是怎么保证的

补丁**不是**简单的全局查找替换。每个字符串都会先判断「代码拿它干什么」：

| 类别 | 处理 | 例子 |
|---|---|---|
| `display` 显示用 | 翻译 | 按钮上的 `Cancel` → `取消` |
| `value` 代码拿去比较 / 当 key / 当 DOM id | **不碰** | `$("exPreset").value === "Custom"` |
| `unknown` 判断不了 | **不碰** | — |

同一个字符串如果既显示又被比较（比如 `Fast`），**整个都不翻**——否则两处会对不上。

另外还有 5 道保险：

1. **`<option>` 没有 `value=` 时，它的文字就是它的值** → 不翻
   （后端会拿这个字符串比较，翻了就坏）
2. **模板字符串** `` `${n}/3 selected` `` → 只翻静态那段，`${n}` 原样不动
3. **代码守卫**：长得像代码的（CSS 选择器、`input[name="x"]`、路径、API 地址）一律不翻
4. **数字守卫**：译文里的数字必须和原文**完全一样**，否则跳过这次替换
5. **自检**：改完立刻验证——
   - `app.js` 必须还能被 node 解析（`node --check`）
   - 所有 `===` 比较用到的字符串必须**一字不差**
   - HTML 标签必须配平（div/button/span/select/option 逐个核对）
   - 中文字符数必须够多
   **任何一项不过就自动回滚**，不会留下改坏的界面。

---

## 已知限制

- **只有 Web UI 界面**是中文的。Fizgig 给训练脚本、ComfyUI 节点、CLI 输出的
  英文不动（改了会破坏和后端的对接）。
- **约 130 个下拉框选项仍然是英文**。它们没有 `value=` 属性，文字本身就是值，
  后端会拿去比较，翻了就坏。这是刻意的取舍。
- **译文由 AI 生成**，见开头的说明。
- **安装后 `git status` 会显示那三个文件被修改**。这不影响使用，但会让
  `git pull` 在上游改动这些文件时冲突。两个办法：
  1. 让 git 忽略本地改动（推荐）：
     ```powershell
     cd <Fizgig 根目录>
     git update-index --skip-worktree src/fizgig/web/static/index.html src/fizgig/web/static/app.js src/fizgig/web/static/style.css
     ```
     上游真的改了它们时要先解开：
     ```powershell
     git update-index --no-skip-worktree src/fizgig/web/static/index.html src/fizgig/web/static/app.js src/fizgig/web/static/style.css
     ```
  2. 实在冲突了：`install.py uninstall` 然后 `install.py install` 就行。
- 少数**人名 / 品牌 / 路径 / 技术标识**保持英文：Fizgig、ComfyUI、LoRA、RunPod、
  Qwen3-VL、VRAM、`.safetensors`、`/workspace/...` 等等。

---

## 目录里都是什么

### 运行时（发布内容）

| 文件 | 作用 |
|---|---|
| **`一键汉化.bat`** | **双击这个**：中文 ↔ 英文 一键切换 |
| **`一键还原英文.bat`** | 双击这个：只还原英文 |
| `install.py` | 命令行入口：安装 / 卸载 / 状态 / 体检 |
| `toggle_zh.py` | `一键汉化.bat` 背后调用的切换脚本 |
| `patchlib.py` | 补丁引擎：分类、替换、自检 |
| `config.py` | 自动找 Fizgig 根目录 |
| `dictionary.json` | **词条表**：1140 条 英文 → 中文 |
| `conflicts.json` | 101 条「既显示又被比较」的词，不翻 |
| `fixups.json` | 手工指定的固定译法（品牌名、单位） |
| `TRANSLATE_RULES.md` | 翻译规则（补词时请先读这个） |

### 开发时用的（不在发布内容里）

`selftest.py`（在副本上跑自检）、`build_vocab.py` / `compute_gap.py` /
`filter_gap.py` / `diag_*.py` / `classify_js.py`（提取与诊断）、
`merge_*.py` / `verify_*.py`（合并与校验）、`parts/`（分批翻译的原始产物）、
`backup/`（安装前的原件备份）。

这些都在 `.gitignore` 里，仓库里不包含。

---

## 以后想改某句译文

1. 在 `dictionary.json` 里找到那一条（键是英文原文），直接改值。
2. 重新安装：
   ```powershell
   python install.py install
   ```
   （先 `uninstall` 再 `install`，或直接双击 `一键汉化.bat` 两次）

**改词表不需要重译全部 1140 条。**

新增词条：把 `{"英文": "中文"}` 加进 `dictionary.json` 即可（不用管 JSON 排序）。

---

## 许可

本补丁是一个独立工具，不修改 Fizgig 的源码仓库结构。

**Apache-2.0**（与 Fizgig 本体一致）。

Fizgig 本身（github.com/shootthesound/Fizgig）版权归其作者
Peter Neill 所有。`dictionary.json` 是其界面文案的翻译作品，
作为衍生作品同样以 Apache-2.0 发布。详见 `NOTICE`。

本项目为非官方工具，与 Fizgig 作者无隶属或背书关系。
