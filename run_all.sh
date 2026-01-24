#!/usr/bin/env bash
set -euo pipefail

# 一键跑完整流程：
# 1) Phase1：EPUB -> 按章 JSONL（前三章）
# 2) Phase2：JSONL -> LLM 分析 JSON
# 3) Phase3：分析 JSON -> Excel 报告
#
# 用法：
#   ./run_all.sh "book/书名.epub"
#   ./run_all.sh "book/书名"
#   ./run_all.sh "书名"
#
# 注意：第二阶段需要你已配置 llm.json 并设置 API Key 环境变量（例如 VOLC_ARK_API_KEY）。

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

if [[ $# -lt 1 ]]; then
  echo "用法：$0 <epub路径|小说目录(book/书名)|书名>"
  exit 2
fi

INPUT="$1"

# 自动准备 llm.json（如果用户还没创建）
if [[ ! -f "llm.json" && -f "llm.example.json" ]]; then
  cp -n "llm.example.json" "llm.json" || true
  echo "[提示] 未发现 llm.json，已从 llm.example.json 复制生成（请确认其中的 provider/profile 配置）。"
fi

NOVEL_DIR=""

if [[ "$INPUT" == *.epub ]]; then
  EPUB_PATH="$INPUT"
  BOOK_NAME="$(basename "$EPUB_PATH")"
  BOOK_NAME="${BOOK_NAME%.epub}"
  NOVEL_DIR="book/$BOOK_NAME"

  echo "[Phase1] 提取前三章：$EPUB_PATH"
  python3 phase1_extract/extract_three_chapters.py "$EPUB_PATH"
elif [[ -f "book/${INPUT}.epub" ]]; then
  EPUB_PATH="book/${INPUT}.epub"
  BOOK_NAME="$INPUT"
  NOVEL_DIR="book/$BOOK_NAME"

  echo "[Phase1] 提取前三章：$EPUB_PATH"
  python3 phase1_extract/extract_three_chapters.py "$EPUB_PATH"
elif [[ -d "$INPUT" ]]; then
  NOVEL_DIR="$INPUT"
elif [[ -d "book/$INPUT" ]]; then
  NOVEL_DIR="book/$INPUT"
else
  echo "输入无效：$INPUT"
  echo "请传入：book/书名.epub 或 book/书名 或 书名"
  exit 2
fi

echo "[Phase2] 生成分析：$NOVEL_DIR"
python3 phase2_analysis/run_phase2.py "$NOVEL_DIR"

echo "[Phase3] 生成 Excel：$NOVEL_DIR"
python3 phase3_excel/run_phase3.py "$NOVEL_DIR"

echo "[完成] 全流程已结束。"
