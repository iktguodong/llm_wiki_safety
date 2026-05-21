# 安牛（AnNiu）

个人安全知识库助手，由杭州了安科技有限公司开发，是一个面向安全生产知识工作者的公益安全项目。

安牛基于 LLM Wiki 构建，支持将用户上传的安全生产、应急预案、合规制度、培训材料等文档转化为结构化 Wiki，并进一步用于知识库问答、原文检索、Wiki 质量检查和培训材料生成。

目标为安全生产知识工作者提供一个专业、可追溯、可检索、可复用的 AI 辅助工具，帮助用户更高效地整理、检索、理解和复用安全知识。

## 主要能力

### 1. 多知识库管理

- 创建、查看、重命名、删除多个独立知识库
- 每个知识库都有自己的原始文档、Wiki 页面、索引和日志
- 支持切换当前知识库

### 2. 文档智能化处理

- 上传 PDF、Word（.doc/.docx）、TXT、Markdown 等文档
- 自动提取文本并触发 LLM 驱动的 Wiki 生成
- 自动维护 `wiki/index.md`、`wiki/log.md` 和文档追踪文件
- 支持手动重新解析文档
- 扫描版 PDF 不做 OCR 兜底，会返回错误提示

### 3. 知识库问答

- 基于知识库 Wiki 内容回答问题（始终知识库优先）
- 优先读取 `wiki/index.md` 结构，再结合相关页面生成答案
- 支持引用多个知识库
- 支持流式（SSE）问答和同步问答
- **未选择知识库时**：若开启联网搜索且有结果则联网回答，否则纯 LLM 通用问答
- **已选择知识库时**：始终仅基于 Wiki 回答，不因无命中而改走联网或通用模型
- 支持自动续写，避免因长度限制出现半截回答

**问答路由（`chat.py`）**

```
用户提问
    ├─ 未选择知识库 → 若 use_web_search 且有检索结果 → 联网回答；否则 → 纯 LLM 通用问答
    └─ 已选择知识库 → 始终基于 Wiki（QA_PROMPT；相关页面可为空，仅依赖索引与模型说明）
```

> **评分规则说明**：向模型注入的「相关页面」列表只收录长度 ≥ 3 字符的关键词命中（标题 +4、摘要 +2、正文 +1、标题节 +0.5）。2 字符词（如「安全」「生产」）在安全生产领域极度通用，若参与评分会导致几乎所有页面都被判为相关，冲淡检索结果。

### 4. 原文检索

- 在原始文档中做关键词模糊搜索
- 返回高亮片段、页码、分数和知识库分组结果
- 适合精确查找原文条款、流程和表述

### 5. Wiki 质量检查（Lint）

- 检查 Wiki 页面格式、链接完整性、孤儿页、来源标注等问题
- 以错误、警告、提示的形式展示结果

### 6. 培训材料生成

- 基于一个或多个知识库内容生成培训大纲
- 支持生成 **PPTX** 文件和独立 **HTML** 文件
- 支持按受众、时长、重点领域、风格进行配置
- 支持实时生成进度查询、生成取消、文件下载与预览
- 内置内容打包、大纲构建、质量检查、幻灯片规划等子系统

### 7. 专业助手

- 预设多种助手定义（安全专家、应急预案、合规顾问等）
- 每个助手有自定义系统提示词，支持快速切换不同问答策略
- 支持助手提示词优化（通过 LLM 改写）

### 8. 模型配置

- 支持多个模型服务提供商（预置 DeepSeek、SiliconFlow、阿里云百炼）
- 支持按用途分配模型角色：
  - `doc_parse`：文档解析
  - `qa_chat`：知识问答
  - `ppt_gen`：PPT 生成
- 支持测试模型连接可用性
- 支持自定义添加/编辑模型服务商

### 9. 文档阅读器

- 内置文档阅读器，支持页面导航
- 支持文本高亮标注，保存/加载高亮状态

### 10. 消息导出

- 支持将对话消息导出为 DOCX 文件

## 页面一览

| 页面 | 说明 |
|---|---|
| 对话 | 基于知识库进行问答，支持多知识库引用、模型切换；未选知识库时可联网或通用 LLM；支持自动续写和消息重新生成 |
| 专业助手 | 预设助手入口，用于快速切换不同问答策略，支持助手提示词优化 |
| 原文检索 | 原文模糊搜索与高亮展示 |
| 知识库管理 | 知识库管理、文档上传、文档解析、Wiki 检查 |
| PPT 生成 | 生成培训大纲、PPTX 和 HTML 培训材料 |
| 设置 | 配置模型服务、API Key、模型角色分配 |
| 关于 | 产品介绍、版本信息、检查更新 |

对话、检索和知识库页面都可以打开阅读器，查看原始文档页面内容。

## 工作流

推荐使用顺序如下：

1. 在「设置」里配置模型服务商、API Key、模型角色分配
2. 在「知识库」里创建知识库
3. 上传原始文档
4. 等待或手动触发解析，生成 Wiki 页面
5. 在「对话」里基于 Wiki 提问
6. 在「原文检索」里查找原文
7. 在「PPT 生成」里生成培训大纲、PPTX 或 HTML 培训材料

## 技术栈

### 后端

- Python 3.10+
- FastAPI（ASGI 框架）
- Pydantic v2（数据校验与模型定义）
- PyMuPDF（PDF 文本提取）
- python-docx + olefile（Word 文档解析）
- python-pptx（PPTX 生成）
- httpx（异步 LLM API 调用）
- beautifulsoup4 + Markdown（文本处理）
- uvicorn（ASGI 服务器）

### 前端

- React 18 + TypeScript
- Vite 6（构建工具）
- Tailwind CSS 4（样式）
- shadcn/ui 风格组件 + Radix UI 原语
- lucide-react 图标
- recharts（图表）

## 项目结构

```text
.
├── backend/                        # FastAPI 后端 (端口 8000)
│   ├── app.py                      # API 入口与路由
│   ├── config.py                   # 全局配置管理 (~/.anniu/config.json)
│   ├── models.py                   # Pydantic 请求/响应数据模型
│   ├── logging_config.py           # 日志配置
│   ├── requirements.txt            # Python 依赖
│   ├── services/                   # 核心业务服务层
│   │   ├── knowledge_base.py       # 知识库 CRUD 与统计
│   │   ├── document.py             # 文档上传、追踪、删除
│   │   ├── wiki.py                 # Wiki 生成与 lint 检查
│   │   ├── chat.py                 # 问答引擎（知识库/通用/联网）
│   │   ├── search.py               # 原文全文搜索
│   │   ├── llm.py                  # LLM 调用封装（OpenAI 兼容接口）
│   │   ├── text_extraction.py      # PDF/Word/TXT/MD 文本提取
│   │   ├── training_html.py        # HTML 培训材料生成
│   │   ├── training_ppt.py         # PPTX 培训生成
│   │   ├── training_downloads.py   # 文件下载解析
│   │   ├── message_export.py       # 对话消息导出为 DOCX
│   │   ├── assistant_prompt.py     # 助手提示词优化
│   │   └── presentation/           # 培训生成子系统
│   │       ├── content_pack.py     # 内容打包
│   │       ├── models.py           # 演示数据模型
│   │       ├── outline_builder.py  # 大纲构建
│   │       ├── pptx_renderer.py    # PPTX 渲染
│   │       ├── project_store.py    # 任务管理与临时上传
│   │       ├── quality_check.py    # 质量验证
│   │       ├── safety_templates.py # 安全领域模板
│   │       └── slide_planner.py    # 幻灯片规划
│   ├── prompts/
│   │   └── AGENTS.md               # Wiki 生成的系统提示词规范
│   └── tests/                      # pytest 测试套件
│       ├── conftest.py
│       ├── test_chat_kb_retrieval.py
│       ├── test_chat_service_web_search.py
│       ├── test_chat_auto_continuation.py
│       ├── test_full_workflow.py
│       ├── test_llm_service.py
│       ├── test_wiki_parallel_pipeline.py
│       ├── test_presentation_outline.py
│       ├── test_presentation_generate.py
│       ├── test_presentation_content_pack.py
│       ├── test_training_html_generation.py
│       ├── test_training_uploads.py
│       ├── test_config.py
│       ├── test_message_export.py
│       └── test_assistant_prompt_optimization.py
├── frontend/                       # React 前端 (端口 5173)
│   ├── index.html
│   ├── vite.config.ts
│   ├── package.json
│   ├── tsconfig.json
│   ├── public/
│   │   ├── anniu-logo.png
│   │   ├── favicon.png
│   │   └── assistant-icons/        # 50+ 助手 SVG 图标
│   └── src/
│       ├── main.tsx                # 应用入口
│       ├── styles/                 # 样式文件
│       │   ├── index.css
│       │   ├── tailwind.css
│       │   └── theme.css
│       ├── lib/
│       │   ├── api.ts              # API 客户端（全端点）
│       │   ├── types.ts            # TypeScript 类型定义
│       │   └── context.tsx         # 全局状态管理
│       └── app/
│           ├── App.tsx             # 根组件与页面路由
│           ├── data/
│           │   ├── assistants.ts   # 预设助手定义
│           │   └── assistant-icons.ts
│           └── components/
│               ├── Sidebar.tsx     # 导航侧边栏
│               ├── StatusBar.tsx   # 底部状态栏
│               ├── ui/             # 50+ UI 组件
│               └── pages/
│                   ├── ChatPage.tsx            # 对话页面
│                   ├── AssistantPage.tsx       # 专业助手页面
│                   ├── SearchPage.tsx          # 原文检索页面
│                   ├── KnowledgeBasePage.tsx   # 知识库管理页面
│                   ├── TrainingPage.tsx        # PPT/HTML 生成页面
│                   ├── SettingsPage.tsx        # 设置页面
│                   ├── AboutPage.tsx           # 关于页面
│                   └── ReaderPage.tsx          # 文档阅读器
├── knowledge-bases/                # 知识库运行时数据（gitignored）
├── data/                           # Wiki 模板与项目级静态素材
├── output/                         # 导出的 PPTX/HTML 等运行时文件
├── docs/                           # 项目文档
│   ├── AGENTS.md
│   ├── product-requirements.md
│   ├── DEVELOPMENT-PLAN.md
│   ├── PROJECT-SETUP.md
│   └── agents/
├── start.sh                        # 后端启动脚本
├── AGENTS.md                       # Agent 技能与项目上下文
└── readme.md
```

## 数据结构

每个知识库通常包含以下内容：

```text
knowledge-bases/<kb_id>/
├── meta.json                       # 知识库元信息与统计数据
├── raw/
│   ├── 原始文档.pdf                # 上传的原始文档
│   └── 文档追踪.json               # 文档 ID、文件名、解析状态、关联 Wiki 页面
└── wiki/
    ├── index.md                    # 知识库导航索引（保留文件）
    ├── log.md                      # Wiki 变更日志（保留文件）
    └── *.md                        # 生成的 Wiki 页面
```

仓库默认不再附带示例知识库内容；`data/templates/` 只保留 Wiki 页面模板，方便本地生成时复用。

## 支持的文档格式

- PDF：`.pdf`（需可提取文本，扫描版不支持）
- Word：`.docx`、`.doc`（.doc 依赖 OLE 结构）
- 文本：`.txt`
- Markdown：`.md`、`.markdown`

## 配置与存储位置

- 配置文件：`~/.anniu/config.json`
- 开发态知识库根目录：`./knowledge-bases/`
- 桌面发布态知识库根目录：`~/.anniu/knowledge-bases/`
- 开发态输出目录：`./output/`
- 桌面发布态输出目录：`~/.anniu/output/`

配置保存内容：

- 当前知识库
- 当前模型
- 模型提供商列表（含 API Key、Base URL、可用模型）
- 模型角色分配（文档解析、知识问答、PPT 生成）
- UI 状态

## API 概览

### 配置

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/config` | 获取全局配置 |
| PUT | `/api/config` | 更新全局配置 |
| POST | `/api/config/models/validate` | 测试模型连接 |
| GET | `/api/config/current-kb` | 获取当前知识库 |
| POST | `/api/config/current-kb` | 设置当前知识库 |
| GET | `/api/config/current-model` | 获取当前模型 |
| POST | `/api/config/current-model` | 设置当前模型 |

### 知识库

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/knowledge-bases` | 列出知识库 |
| POST | `/api/knowledge-bases` | 创建知识库 |
| GET | `/api/knowledge-bases/{kb_id}` | 获取知识库详情 |
| PUT | `/api/knowledge-bases/{kb_id}` | 重命名知识库 |
| DELETE | `/api/knowledge-bases/{kb_id}` | 删除知识库 |

### 文档

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/knowledge-bases/{kb_id}/documents` | 列出文档 |
| POST | `/api/knowledge-bases/{kb_id}/documents` | 上传文档 |
| GET | `/api/knowledge-bases/{kb_id}/documents/{doc_id}/delete-preview` | 删除预览 |
| DELETE | `/api/knowledge-bases/{kb_id}/documents/{doc_id}` | 删除文档 |
| GET | `/api/knowledge-bases/{kb_id}/documents/{doc_id}/content` | 获取文档内容 |
| POST | `/api/knowledge-bases/{kb_id}/documents/{doc_id}/highlights` | 保存高亮 |
| GET | `/api/knowledge-bases/{kb_id}/documents/{doc_id}/highlights` | 获取高亮 |

### Wiki

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/knowledge-bases/{kb_id}/wiki-pages` | 列出 Wiki 页面 |
| GET | `/api/knowledge-bases/{kb_id}/wiki-pages/{page_name}` | 获取 Wiki 页面内容 |
| POST | `/api/knowledge-bases/{kb_id}/documents/{doc_id}/parse` | 触发文档解析与 Wiki 生成 |
| POST | `/api/knowledge-bases/{kb_id}/wiki-lint` | 执行 Wiki 质量检查 |

### 对话

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/chat` | 流式问答（SSE） |
| POST | `/api/chat/sync` | 同步问答 |
| POST | `/api/chat/export` | 导出对话消息为 DOCX |

### 检索

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/search` | 原文关键词搜索 |

### 培训

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/training/outline` | 生成培训大纲 |
| POST | `/api/training/generate` | 生成 PPTX |
| POST | `/api/training/html` | 生成 HTML 培训材料 |
| GET | `/api/training/progress/{job_id}` | 查询生成进度 |
| POST | `/api/training/cancel/{job_id}` | 取消生成任务 |
| GET | `/api/training/download/{filename}` | 下载生成文件 |
| GET | `/api/training/preview/{filename}` | 预览生成文件 |
| POST | `/api/training/cleanup` | 清理临时文件 |

### 助手

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/assistants` | 获取助手定义列表 |
| POST | `/api/assistants/optimize-prompt` | 优化助手提示词 |

## 快速开始

### 1. 环境要求

### 1.1 桌面客户端（Electron，v1.0.0）

当前仓库已经补了 Electron 桌面壳和 GitHub Release 打包流程：

- 前端入口：`frontend/`
- 桌面主进程：`frontend/electron/main.js`
- 发布工作流：`/.github/workflows/release-electron.yml`

本地开发可先跑：

```bash
cd frontend
npm install
npm run electron:dev
```

当前发布链路会在 GitHub Actions 中先把后端打成可执行文件，再用 Electron 生成 macOS 安装包并发布到 GitHub Release。  
现阶段这条流水线先覆盖 macOS；如果后续要补 Windows / Linux，可以在同一套 Electron 配置上继续扩展。

- Python 3.10+
- Node.js 18+
- npm 9+

### 2. 启动后端

```bash
./start.sh
```

或手动启动：

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r backend/requirements.txt
python3 -m backend.app
```

后端默认运行在 `http://localhost:8000`，Swagger 文档在 `http://localhost:8000/docs`

### 3. 启动前端

```bash
cd frontend
npm install
npm run dev
```

前端默认运行在 `http://localhost:5173`

## 使用方式

1. 打开前端页面
2. 在「设置」里配置模型服务商和 API Key
3. 创建知识库
4. 上传原始文档
5. 等待自动解析生成 Wiki
6. 在「对话」里提问，或在「原文检索」里搜索原文
7. 在「PPT 生成」里生成大纲、PPTX 或 HTML 培训材料

## 开发说明

- 前端会定时同步知识库和配置状态
- 聊天页面会把部分会话状态保存在浏览器 localStorage 中
- 文档上传后会自动触发解析任务
- Wiki 生成时会读取 `backend/prompts/AGENTS.md` 作为工作流规范
- 后端和前端的数据模型需要保持一致，修改接口后要同步更新 `backend/models.py` 和 `frontend/src/lib/types.ts`

## 常见注意点

- `wiki/index.md` 和 `wiki/log.md` 是保留文件，不要被普通 Wiki 页面覆盖
- 删除文档时要注意是否同时删除关联 Wiki 页面
- 生成 Wiki 时不要编造来源、阈值、职责或流程
- 如果模型配置不完整，文档解析和问答会失败
- 前端和助手的消息操作（复制、导出、删除、重新生成）需保持一致

## 测试与验证

后端测试位于 `backend/tests/`，包含 15+ 测试文件。修改后端逻辑时，建议至少检查：

- 知识库创建与删除
- 文档上传与追踪
- Wiki 生成与 lint
- 问答路由与检索返回结构
- 培训大纲、PPTX 与 HTML 导出
- 消息导出
- 助手提示词优化

## 参考文档

- [产品需求文档](docs/product-requirements.md)
- [项目开发计划](docs/DEVELOPMENT-PLAN.md)
- [仓库级 Agent 说明](AGENTS.md)
- [后端 Wiki 生成规范](backend/prompts/AGENTS.md)
