# Fizgig 汉化补丁（简体中文）

把 [Fizgig](https://github.com/shootthesound/Fizgig) 的网页界面（Web UI）改成简体中文。
**只改界面文字，不动任何功能、配置或数据。**

> **⚠️ 翻译由 AI 完成**
> 词表由 AI（DeepSeek 等大模型）按 `TRANSLATE_RULES.md` 批量翻译，**未经母语者逐条校对**。
> 个别用词可能不够地道。觉得哪里别扭，直接改 `dictionary.json` 里那一条再重新安装即可。

**适配版本：Fizgig v8.9.93（2026-10-28，commit 98de7a48）**

---

## 一分钟上手

### 放在哪？

推荐放在 Fizgig 根目录里，名字叫 `zh_patch`：

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

放别处也行：在文件夹里建 `fizgig_root.txt`（写 Fizgig 根目录），或设 `FIZGIG_ROOT` 环境变量。
判定标准：目录里**同时有** `fizgig.py` 和 `src/fizgig/web/static/`。

### 三个 .bat

| 双击这个 | 作用 |
|---|---|
| **`一键汉化.bat`** | 中文 ↔ 英文 一键切换 |
| **`一键还原英文.bat`** | 只还原英文 |
| **`一键更新并汉化.bat`** | **更新 Fizgig 的正确姿势**：先还原英文 → 跑官方更新 → 再汉化。更新完重启 Fizgig 即可 |

改完请**重启 Fizgig**（或浏览器里 `Ctrl+F5`）。

命令行等价写法（`$PY` = Fizgig 的 `venv\Scripts\python.exe`）：

```powershell
& $PY install.py install     # 安装 / 重新安装
& $PY install.py uninstall   # 还原英文
& $PY install.py status      # 当前状态
& $PY install.py check       # 只体检，不改文件
& $PY update_zh.py           # 更新 + 重新汉化
```

---

## 「更新了却还提示可以更新」是怎么回事

**不是汉化本身的 bug，是汉化和 git 撞车了。**

汉化会改动 `src/fizgig/web/static/` 下的三个文件，而这三个文件**上游也在改**。
`git pull` 遇到「本地有改动 + 上游也改了同一个文件」时会直接中止：

```
error: Your local changes to the following files would be overwritten by merge:
        src/fizgig/web/static/app.js
Please commit your changes or stash them before you merge.
```

而 Fizgig 自带的 `update_fizgig.py` **不检查 `git pull` 的返回值**，接着装依赖、
最后照样打印「Update complete!」，所以看起来像更新成功了，其实 HEAD 一步没动，
About 框里自然还是「有新版本」。

**现在的解法**：`一键更新并汉化.bat`（内部是 `update_zh.py`）按正确顺序做三件事：

1. `git checkout` 把那三个文件还原成上游版本（这一步同时解决了冲突）
2. 调用 Fizgig 官方的 `update_fizgig.py`（它自己会认 CUDA / ROCm、装依赖）
3. 更新成功后重新打汉化

脚本还会在更新后对比 `HEAD..origin/master` 的落后提交数：如果一次都没变少，
会明确告诉你「这次的 pull 又被挡住了」，而不是假装成功。

---

## 它到底改了什么

只有三个静态文件：

```
src/fizgig/web/static/index.html
src/fizgig/web/static/app.js
src/fizgig/web/static/style.css
```

两层翻译：

1. **源码层**（`patchlib.py`）：逐条判断每个字符串「代码拿它干什么」——
   显示用的翻译，代码用来比较 / 当 key / 当 DOM id / 当 `<option>` 的 value 的一律不碰。
   同一句话只要在**任何地方**被当值用过，整句都不翻（否则两处会对不上）。
2. **运行时层**（`zh_runtime.js`，注入到 index.html 的 `</body>` 前）：
   翻译**运行时才出现**的文字——后端返回的报错、弹窗、动态拼出来的句子、
   没有 `value=` 的下拉选项（先把英文 value 固定下来再翻标签）、`confirm/alert/prompt`。
   它用 `MutationObserver` 跟着 DOM 走，所以点出来、弹出来的界面也是中文。

**没有碰**：`prefs.json`、`user_data/`（模型、LoRA、预设、缓存）、`output_loras/`、
训练数据、**任何 Python 后端代码**、任何配置。

---

## 安全性

1. **分类替换**：显示组 → 翻译；值组 / 判断不出 → 不碰。
2. **比较字面量守卫**：改完检查 `app.js` 里所有 `===`/`!==` 用到的字符串一字未变，变了就整批回滚。
3. **数字守卫**：译文里的数字必须和原文一致（顺序可以不同），否则跳过该条。
4. **代码守卫**：长得像代码的（CSS 选择器、路径、URL、正则片段）一律不翻。
5. **语法自检**：`node --check app.js`；HTML 标签逐个配平；`<script>` 只多一个。
6. **只靠脚本就能还原（不依赖 git）**：安装时把「改了哪几个字节、原文是什么」
   写进 `rollback.json`，还原时按字节原样倒回去，并用 sha256 校验每个文件。
   实测：**装 → 卸 之后三个文件和原件逐字节相同**（CRLF 也不变）。
   顺手备份到 `backup/<时间戳>/`，git 只当最后的兜底。
7. **幂等**：安装前先用 rollback.json 把自己还原成英文再打补丁，所以连按两次
   `一键汉化` 结果完全一样，不会「翻上加翻」。

> 也就是说：**只需要 `zh_patch` 这个文件夹**，不需要 git、不需要联网、
> 不需要手动备份，双击 .bat 就能汉化，再双击就能还原。

任何一项不过 → **自动回滚**，不留半成品。

---

## 已知限制

- **只有 Web UI 界面**是中文。训练脚本、ComfyUI 节点、命令行输出保持英文。
- **少数词故意保持英文**：既当显示又当判断标准的词（如 `Show mask`、`Web UI`），
  翻了会让代码认不出它。这类词在 `skip.json` 里。
- **译文由 AI 生成**，见开头说明。

---

## 目录里都是什么

| 文件 | 作用 |
|---|---|
| **`一键汉化.bat`** / **`一键还原英文.bat`** | 双击切换中英文 |
| **`一键更新并汉化.bat`** | 更新 Fizgig 后再汉化（推荐用它更新） |
| `install.py` | 安装 / 卸载 / 状态 / 体检 |
| `update_zh.py` | 更新流程（还原 → 官方更新 → 重新汉化） |
| `toggle_zh.py` | `一键汉化.bat` 背后调用的切换脚本 |
| `patchlib.py` | 源码层补丁引擎：分类、替换、自检 |
| `build_pack.py` | 把词表编译成 `zh_pack.js` |
| `zh_runtime.js` | 运行时翻译器（DOM / 弹窗 / 下拉选项） |
| `zh_pack.js` | 编译产物：`window.FIZGIG_ZH = {exact, templates, skip}`（**由 build_pack.py 生成，别手改**） |
| `dictionary.json` | **词条表**：英文 → 中文（当前 2182 条） |
| `templates.json` | 带变量的句子模板（`\u0000` 是变量占位） |
| `skip.json` | 永远不翻的词（代码要读回去比较的） |
| `rollback.json` | **还原记录**：改了哪几个字节、原文是什么（本地状态，不入库） |
| `conflicts.json` | 旧版遗留的「既显示又被比较」词表，仍然生效 |
| `config.py` | 自动找 Fizgig 根目录 |
| `TRANSLATE_RULES.md` | 翻译规则（补词前先读） |

---

## 想改某句译文 / 加词条

1. 改 `dictionary.json`（键是英文原文，值是中文）。
2. 重新编译并安装：

```powershell
& $PY build_pack.py
& $PY install.py install
```

**改词表不需要重译全部。**

如果某句在新版本里没被翻到：多半是上游改了那句话的原文。
把界面上那句英文抄下来，加进 `dictionary.json` 即可（大小写、标点要完全一致）。

---

## 许可

本补丁是独立工具，不修改 Fizgig 的源码仓库结构，也从不向它提交任何东西。

**Apache-2.0**（与 Fizgig 本体一致）。

Fizgig 本身（github.com/shootthesound/Fizgig）版权归其作者 Peter Neill 所有。
`dictionary.json` 是其界面文案的翻译作品，作为衍生作品同样以 Apache-2.0 发布。详见 `NOTICE`。

本项目为非官方工具，与 Fizgig 作者无隶属或背书关系。