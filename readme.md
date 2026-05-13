# 安牛（AnNiu）

安牛是一个本地运行的企业安全知识库应用，用 LLM 把上传的文档转成结构化 Wiki，再把这些 Wiki 用于问答、原文检索和培训材料生成。

它面向企业安全管理、应急预案、合规制度、培训材料等内容场景，重点不是“聊天机器人”，而是“可追溯、可检索、可复用的知识库工作流”。

## 主要能力

### 1. 多知识库管理

- 创建、查看、删除多个独立知识库
- 每个知识库都有自己的原文、Wiki 页面、索引和日志
- 支持切换当前知识库

### 2. 文档智能化处理

- 上传 PDF、Word、TXT、Markdown 等文档
- 自动提取文本并触发 Wiki 生成
- 自动维护 `wiki/index.md`、`wiki/log.md` 和文档追踪文件
- 支持手动重新解析文档

### 3. 知识库问答

- 基于知识库 Wiki 内容回答问题
- 优先读取 `wiki/index.md` 结构，再结合相关页面生成答案
- 支持引用多个知识库
- 支持流式问答和同步问答
- 支持联网搜索兜底
- 支持自动续写，尽量避免因为长度限制而出现半截回答

### 4. 原文检索

- 在原始文档中做关键词模糊搜索
- 返回高亮片段、页码、分数和知识库分组结果
- 适合精确查找原文条款、流程和表述

### 5. Wiki 质量检查

- 检查 Wiki 页面格式、链接、孤儿页、来源标注等问题
- 以错误、警告、提示的形式展示结果

### 6. 培训材料生成

- 基于一个或多个知识库内容生成培训大纲
- 生成 PPTX 文件
- 支持按受众、时长、重点领域进行配置

### 7. 模型配置

- 支持多个模型服务提供商
- 支持按用途分配模型角色
  - `doc_parse`
  - `qa_chat`
  - `ppt_gen`

## 页面一览

| 页面 | 说明 |
|---|---|
| 对话 | 基于知识库进行问答，支持多知识库引用、模型切换、联网兜底、自动续写和消息重新生成 |
| 助手 | 预设助手入口，用于快速切换不同问答策略，支持消息重新生成 |
| 检索 | 原文模糊搜索与高亮展示 |
| 知识库 | 知识库管理、文档上传、文档解析、Wiki 检查 |
| 培训 | 生成培训大纲和 PPT |
| 设置 | 配置模型服务、API Key、当前知识库、当前模型 |

对话、检索和知识库页面都可以打开阅读器，查看原始文档页面内容。

## 工作流

推荐使用顺序如下：

1. 在「设置」里配置模型服务商、API Key、当前模型角色
2. 在「知识库」里创建知识库
3. 上传原始文档
4. 等待或手动触发解析，生成 Wiki 页面
5. 在「对话」里基于 Wiki 提问
6. 在「检索」里查原文
7. 在「培训」里生成培训大纲或 PPT

## 技术栈

### 后端

- Python 3.10+
- FastAPI
- Pydantic
- PyMuPDF
- python-docx
- olefile
- python-pptx
- httpx

### 前端

- React 18
- TypeScript
- Vite
- Tailwind CSS
- shadcn/ui 风格组件
- Radix UI
- lucide-react 图标

## 项目结构

```text
.
├── backend/                    # FastAPI 后端
│   ├── app.py                  # API 入口
│   ├── config.py               # 全局配置、路径与知识库目录
│   ├── models.py               # 请求/响应数据模型
│   ├── requirements.txt        # Python 依赖
│   ├── services/               # 核心业务服务
│   │   ├── knowledge_base.py   # 知识库 CRUD 与统计
│   │   ├── document.py         # 文档上传、删除、追踪
│   │   ├── wiki.py             # Wiki 生成与 lint
│   │   ├── chat.py             # 问答与联网兜底
│   │   ├── search.py           # 原文检索
│   │   ├── training.py         # 大纲与 PPT 生成
│   │   ├── llm.py              # 模型调用封装
│   │   └── text_extraction.py  # 文本抽取
│   └── prompts/
│       └── AGENTS.md           # Wiki 生成的提示词规范
├── frontend/                   # React 前端
│   ├── src/app/                # 页面与组件
│   ├── src/lib/                # API、类型、全局状态
│   └── src/main.tsx            # 前端入口
├── knowledge-bases/            # 每个知识库的持久化内容
├── data/                       # 样例/参考内容
├── output/                     # 导出的 PPT 等文件
├── start.sh                    # 后端启动脚本
└── readme.md
```

## 数据结构

每个知识库通常包含以下内容：

```text
knowledge-bases/<kb_id>/
├── meta.json
├── raw/
│   ├── 原始文档.pdf
│   └── 文档追踪.json
└── wiki/
    ├── index.md
    ├── log.md
    └── *.md
```

### 关键文件说明

- `meta.json`：知识库元信息、统计数据、文档记录
- `raw/`：原始上传文件
- `raw/文档追踪.json`：文档 ID、文件名、解析状态、关联 Wiki 页面
- `wiki/index.md`：知识库导航索引
- `wiki/log.md`：Wiki 变更日志

## 支持的文档格式

- PDF：`.pdf`
- Word：`.docx`、`.doc`
- 文本：`.txt`
- Markdown：`.md`、`.markdown`

说明：

- PDF 需要是可提取文本的文档
- 扫描版 PDF 不做 OCR 兜底
- `.doc` 解析依赖 OLE 结构，损坏文件可能无法提取

## 配置与存储位置

- 配置文件：`~/.anniu/config.json`
- 知识库根目录：`./knowledge-bases/`
- 输出目录：`./output/`

配置里会保存：

- 当前知识库
- 当前模型
- 模型提供商列表
- 模型角色分配
- UI 状态

## API 概览

### 配置

- `GET /api/config`
- `PUT /api/config`
- `POST /api/config/models/validate`
- `GET /api/config/current-kb`
- `POST /api/config/current-kb`
- `GET /api/config/current-model`
- `POST /api/config/current-model`

### 知识库

- `GET /api/knowledge-bases`
- `POST /api/knowledge-bases`
- `GET /api/knowledge-bases/{kb_id}`
- `DELETE /api/knowledge-bases/{kb_id}`

### 文档

- `GET /api/knowledge-bases/{kb_id}/documents`
- `POST /api/knowledge-bases/{kb_id}/documents`
- `GET /api/knowledge-bases/{kb_id}/documents/{doc_id}/delete-preview`
- `DELETE /api/knowledge-bases/{kb_id}/documents/{doc_id}`
- `GET /api/knowledge-bases/{kb_id}/documents/{doc_id}/content`
- `POST /api/knowledge-bases/{kb_id}/documents/{doc_id}/highlights`
- `GET /api/knowledge-bases/{kb_id}/documents/{doc_id}/highlights`

### Wiki

- `GET /api/knowledge-bases/{kb_id}/wiki-pages`
- `GET /api/knowledge-bases/{kb_id}/wiki-pages/{page_name}`
- `POST /api/knowledge-bases/{kb_id}/documents/{doc_id}/parse`
- `POST /api/knowledge-bases/{kb_id}/wiki-lint`

### 对话

- `POST /api/chat`
- `POST /api/chat/sync`

### 检索

- `POST /api/search`

### 培训

- `POST /api/training/outline`
- `POST /api/training/generate`
- `GET /api/training/download/{filename}`

## 快速开始

### 1. 准备环境

- Python 3.10+
- Node.js 18+
- npm 9+

### 2. 启动后端

```bash
./start.sh
```

或者手动启动：

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r backend/requirements.txt
python3 -m backend.app
```

后端默认运行在 `http://localhost:8000`

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
6. 在「对话」里提问，或在「检索」里搜索原文
7. 在「培训」里生成大纲或 PPT

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

## 测试与验证

后端测试位于 `backend/tests/`。修改后端逻辑时，建议至少检查：

- 知识库创建与删除
- 文档上传与追踪
- Wiki 生成与 lint
- 问答与检索返回结构
- 培训大纲与 PPT 导出

## 参考文档

- [产品需求文档](docs/product-requirements.md)
- [项目开发计划](docs/DEVELOPMENT-PLAN.md)
- [仓库级 Agent 说明](AGENTS.md)
- [后端 Wiki 生成规范](backend/prompts/AGENTS.md)
