# Three-Golden-Chapters

AI 拆解黄金三章，逐段简述内容、拆解节奏、提取爆点，并生成 excel 分析报告。

# Step 1 - 清洗数据：从 EPUB 提取前三章

目标：从 `book/` 目录下的 epub 电子书中，按章节标题识别并只提取前三章，输出为与小说同名的 `jsonl`。

## 章节标题识别规则

脚本会把以下形式的“单行文本块”视为章节标题：

- `第 x 章/节/回 书名`（x 支持阿拉伯数字或常见中文数字）
- `x、书名`
- `x. 书名` / `x．书名`

实现上会优先使用更稳的 `第 x 章/节/回 ...` 作为分章边界；只有在未找到足够章节时，才会回退到 `x、...` / `x. ...` 风格（并尽量用“书名匹配”减少误判）。

## 输出格式

输出文件：`book/小说名.jsonl`（与 epub 同名，仅扩展名变为 `.jsonl`）

每行一个 JSON 对象，包含两个字段：

- `paragraph_id`：段号，从 1 开始
- `text`：本段内容（包含章节标题行）

## 使用方法

1) 把 epub 放到 `book/` 目录下（例如：`book/xxx.epub`）

2) 运行：

```sh
python3 phase1_extract/extract_three_chapters.py book/书名.epub
```

无论输入路径在哪里，输出都会写到 `book/` 目录下，与 epub 同名的 `.jsonl`。
