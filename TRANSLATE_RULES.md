# Fizgig 汉化翻译规则（简体中文）

## 目标
Fizgig 是一个 LoRA / 微调训练工作台。界面文案要像**真实产品 UI**，不是逐词直译。
句子要短、术语要准、按钮要短。

## 绝不翻译（保持原样）
- **产品名 / 品牌**：Fizgig、ComfyUI、LoRA、ReFLoRA、RefMod、RunPod、Gizmo、Krea、Flux、Qwen、MOSS-Image、Hugging Face、OpenMOSS、Kromoss、MiniMax、LongLook、Angelo、Pod
- **技术标识**：VRAM、RAM、GPU、VAE、CUDA、PNG、MP4、GIF、JSON、safetensors、checkpoint、epoch、seed、prompt、token、slider、mod、block、rank
- **路径与 URL**：`/workspace/...`、`github.com/...`
- **emoji**：直接保留
- **单位后缀**：GB、MB、GB+、/hr、MP

## 格式硬规则
1. **占位符 / 数字 / 选项标记位置不变**：
   - `"0/3 selected"` → `"已选 0/3"`
   - `": 0 off, 1 as stored."` → `"：0 为关闭，1 为原样。"`
   - `"All epochs"` → `"所有轮次"`
2. **以标点开头的片段，保留开头标点**：
   - `": how many times it rides in the bundle"` → `"：在包中参与的次数"`
   - `"; on your own server"` → `"；在你自己的服务器上"`
3. **`=` 号说明句**：翻译词，保留数字和 `=`：
   - `"0 = base model (no LoRA); 1.0 = trained strength"` → `"0 = 基础模型（无 LoRA）；1.0 = 训练后的强度"`
4. **按钮标签**：2–6 个汉字，不加句号。
5. **句子**：英文没有句号就不加句号。
6. **不要合并、拆分、增删含义**。每条输入对应一条输出。

## 风格示例
| English | 中文 |
|---|---|
| `Cancel` | `取消` |
| `Add to queue` | `加入队列` |
| `Clear queue` | `清空队列` |
| `Training folder` | `训练文件夹` |
| `Deploy on RunPod` | `部署到 RunPod` |
| `Buy me a coffee` | `请我喝杯咖啡` |
| `Check for updates` | `检查更新` |
| `File manager` | `文件管理器` |
| `Don't show this again` | `不再显示` |
| `Anchor to original` | `锚定到原图` |
| `Auto-Suggest drift` | `自动建议漂移` |
| `Find & Replace` | `查找替换` |
| `Between two dates…` | `两个日期之间…` |

## 长句
长句（说明文字、提示）要拆成自然的中文短句，用中文标点。
不要逐字对译，读起来要像中文软件里的说明。

## 硬性要求
- 输出必须是合法 UTF-8 JSON 对象，键与输入字符串**逐字节相同**
- 键数量必须与输入数组长度相同
- 值里若含英文双引号，写成 `\"`
- 不要有多余的逗号
