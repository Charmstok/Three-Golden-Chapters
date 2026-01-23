# Three-Golden-Chapters

AI 拆解黄金三章，逐段简述内容、拆解节奏、提取爆点，并生成 excel 分析报告。

---

# Step 1：提取前三章（EPUB -> 按章 JSONL）

目标：从 epub 电子书中按章节标题识别并只提取前三章，输出为每章一个 JSONL 文件。

## 使用方法

1) 把 epub 放到 `book/` 目录下（例如：`book/xxx.epub`）

2) 运行：

```sh
python3 phase1_extract/extract_three_chapters.py book/书名.epub
```

无论输入路径在哪里，输出都会写到 `book/书名/` 目录下（每章一个 JSONL 文件）。

## 输出格式

- `book/书名/1_章节名.jsonl`
- `book/书名/2_章节名.jsonl`
- `book/书名/3_章节名.jsonl`

每行一个 JSON 对象，包含两个字段：

- `paragraph_id`：段号，从 1 开始
- `text`：本段内容（章节标题不占用 paragraph_id）

## 章节标题识别规则

脚本会把以下形式的“单行文本块”视为章节标题：

- `第 x 章/节/回 书名`（x 支持阿拉伯数字或常见中文数字）
- `x、书名`
- `x. 书名` / `x．书名`

实现上会优先使用更稳的 `第 x 章/节/回 ...` 作为分章边界；只有在未找到足够章节时，才会回退到 `x、...` / `x. ...` 风格（并尽量用“书名匹配”减少误判）。

---

# Step 2：发送给大模型做拆解（JSONL -> 分析 JSON）

目标：把 Step 1 的每章 JSONL 发送给大模型，输出结构化的剧情块（chunk/slice）分析 JSON。

## 使用方法

```powershell
Copy-Item llm.example.json llm.json
$env:VOLC_ARK_API_KEY="你的key"
python phase2_analysis/run_phase2.py "book/书名"
```

Linux/macOS（bash/zsh）：

```sh
cp llm.example.json llm.json
export VOLC_ARK_API_KEY="你的key"
python3 phase2_analysis/run_phase2.py "book/书名"
```

也可以只渲染提示词不发起请求（用于检查输入长度/格式）：

```powershell
python phase2_analysis/run_phase2.py --dry-run "book/书名"
```

Linux/macOS（bash/zsh）：

```sh
python3 phase2_analysis/run_phase2.py --dry-run "book/书名"
```

提示词位置：

- `prompt/system.md`
- `prompt/prompt_1.md`
- `prompt/prompt_23.md`

输入支持：

- `book/书名`（目录，包含 `1_*.jsonl`、`2_*.jsonl`、`3_*.jsonl`）
- `book/书名.epub`（会自动定位到 `book/书名/`）

LLM 配置与调用：

- 配置文件：`llm.json`（可由 `llm.example.json` 复制生成）
- provider 调用实现：`llm_provider/`（火山方舟 Chat Completions）
- 请求参数：`max_tokens=10000`（见 `llm_provider/volc_ark_chat.py`）

## 输出格式

输出：

- `book/书名/analysis/1_章节名.json`、`2_章节名.json`、`3_章节名.json`
- `book/书名/analysis/1_章节名.raw.txt` 等（模型原始输出）

其中每个 `chunk` 会包含字段 `chunk_title`（该 chunk 的简要标题）。
