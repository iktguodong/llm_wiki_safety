# 安牛（AnNiu）

企业个人知识库桌面客户端。基于 LLM 自动将文档转化为结构化 Wiki，支持知识库问答、原文检索和培训材料生成。

## 核心功能

### 1. 多知识库管理
- 创建、切换、删除多个独立知识库
- 每个知识库拥有独立的文档、Wiki 页面和索引

### 2. 文档智能化处理
- 支持上传 PDF、Word、Markdown 等格式
- AI 自动解析文档内容，生成结构化 Wiki 页面
- 自动更新 wiki/index.md 索引和 wiki/log.md 操作日志

### 3. 双模式查询
- **知识库问答**：AI 理解问题，基于 Wiki 内容生成答案
  - 提问时系统优先读取 `wiki/index.md` 索引，快速定位知识结构
  - 再结合相关 Wiki 页面综合回答
- **原文检索**：精确匹配关键词，支持高亮展示原文片段

### 4. Wiki 质量检查
- 在「知识库」页面点击「检查 Wiki」按钮
- 自动检查页面格式、链接完整性、孤儿页面、来源标注等质量问题
- 按错误 / 警告 / 提示三级分类展示结果

### 5. 培训材料生成
- 基于单个或多个知识库内容生成培训大纲
- 自动制作 PPT 培训材料
- 支持配置受众、时长、重点等参数

### 6. 多模型配置
- 支持 DeepSeek、OpenAI 等多种 LLM 提供商
- 不同任务可配置不同模型（解析 / 问答 / PPT 生成）

## 界面功能速览

| 页面 | 功能 |
|------|------|
| 对话 | 基于知识库进行 AI 问答，支持多知识库同时引用 |
| 检索 | 原文模糊搜索 / 精确匹配，带高亮和评分 |
| 知识库 | 管理知识库、上传文档、解析文档、检查 Wiki 质量 |
| 培训 | 从知识库生成培训大纲和 PPT |
| 设置 | 配置 LLM 模型提供商、API 密钥、模型角色分配 |

**文档上传后的操作流**：
1. 在「知识库」页面上传文档
2. 系统自动解析生成 Wiki 页面
3. 前往「对话」页面基于知识库提问，或「检索」页面搜索原文

## 技术栈

**后端**
- Python 3.10+
- FastAPI + Pydantic
- PyMuPDF / python-docx（文档解析）
- python-pptx（PPT 生成）

**前端**
- React 18 + TypeScript
- Tailwind CSS 4 + shadcn/ui
- Vite 6

## 项目结构

```
.
├── backend/              # FastAPI 后端
│   ├── app.py            # 主应用，API 路由
│   ├── models.py         # Pydantic 数据模型
│   ├── config.py         # 配置管理
│   ├── services/         # 业务服务（知识库、文档、Wiki、问答、检索、培训）
│   └── prompts/
│       └── AGENTS.md     # LLM Wiki 工作流规范，自动注入 system prompt
├── frontend/             # React 前端
│   ├── src/
│   │   ├── app/          # 页面组件
│   │   ├── lib/          # API 封装、类型定义、全局状态
│   │   └── main.tsx      # 应用入口
│   ├── package.json
│   └── vite.config.ts
├── knowledge-bases/      # 知识库存储目录
├── data/                 # 运行时数据
└── output/               # 生成的 PPT 等输出文件
```

## 快速开始

### 启动后端

```bash
cd backend
pip install -r requirements.txt
python app.py
```

后端服务默认运行在 `http://localhost:8000`

### 启动前端

```bash
cd frontend
npm install
npm run dev
```

前端开发服务器默认运行在 `http://localhost:5173`

### 使用

1. 打开前端页面，先在「设置」中配置 LLM 模型（API 密钥、Base URL）
2. 在「知识库」页面创建知识库并上传文档
3. 等待文档解析完成后，即可在「对话」页面提问或在「检索」页面搜索
