# 📚 黄金三章

**用 AI 拆解小说开篇，读懂剧情、节奏与爆点。**

![Vue 3](https://img.shields.io/badge/Vue-3-42b883)
![Python](https://img.shields.io/badge/Python-3.10%2B-3776ab)
[![MIT License](https://img.shields.io/badge/License-MIT-blue)](LICENSE)

上传一本 EPUB，在浏览器中分析前三章，把阅读积累变成创作参考。

## ✨ 功能

- **章节提取**：自动识别 EPUB 前三章，保留原文与段落编号。
- **AI 拆解**：逐段分析剧情、叙事节奏与爆点，关联上下章内容。
- **自由选模**：支持 OpenAI 兼容的 Chat Completions 和 Responses 接口。
- **网页配置**：管理多组模型、测试连接、切换默认模型，无需手动填写配置文件。
- **报告导出**：在线阅读分析结果，下载 Excel 或 JSON 报告。

## 🚀 快速开始

准备 Python 3.10+、Node.js 22.18+ / 24.12+ 和 [uv](https://docs.astral.sh/uv/)，在项目根目录启动后端：

```sh
uv sync --locked
uv run uvicorn backend.app.main:app --reload --host 127.0.0.1 --port 8000
```

新开一个终端，启动前端：

```sh
cd frontend
npm ci
npm run dev
```

打开 [http://127.0.0.1:5173](http://127.0.0.1:5173)，进入 **模型设置**，填写接口地址、API Key 和模型 ID。保存后上传 EPUB，点击 **开始拆解** 即可。

> 支持最大 50 MB 的 EPUB。模型调用费用由你使用的服务商收取。

## ⚙️ 模型与数据

- Base URL 可填写 API 根地址或完整接口地址；以 `/responses` 结尾时自动识别为 Responses，使用根地址时可手动选择接口格式。
- 密钥保存在后端，保存后不回传原文；编辑时留空保留原密钥，也可替换或清除。
- 书籍、报告和模型配置保存在 `data/`。可通过 `TGC_DATA_DIR` 更换目录，备份时请妥善保管其中的密钥。

## 📦 构建运行

在项目根目录执行，由 Python 同时提供前端页面与 API：

```sh
npm --prefix frontend ci
npm --prefix frontend run build
uv run --no-dev uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --workers 1
```

访问 [http://127.0.0.1:8000](http://127.0.0.1:8000)，API 文档见 [/docs](http://127.0.0.1:8000/docs)。

当前面向个人本机使用，采用单进程后台任务，暂不提供登录和权限隔离。

## 🛠️ 开发

技术栈：**Vue 3 · TypeScript · Vite · FastAPI · SQLite**

```sh
uv run pytest
npm --prefix frontend run build
```

后端代码位于 `backend/`，前端位于 `frontend/`，分析提示词位于 `backend/prompts/`。测试使用模拟模型，不调用付费接口。

