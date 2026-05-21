# 安牛后端服务

## 技术栈

- Python 3.10+
- FastAPI
- Pydantic
- PyMuPDF (PDF解析)
- python-docx (Word .docx 解析)
- olefile (Word .doc 解析)
- python-pptx (PPT生成)

## 目录结构

```
backend/
├── app.py              # FastAPI主应用，所有API端点
├── config.py           # 配置管理（模型、知识库路径）
├── models.py           # Pydantic数据模型
├── requirements.txt    # Python依赖
├── services/           # 业务服务层
│   ├── knowledge_base.py   # 知识库CRUD
│   ├── document.py         # 文档上传/删除
│   ├── wiki.py             # 文档解析、Wiki生成
│   ├── chat.py             # 知识问答
│   ├── search.py           # 原文检索
│   ├── training.py         # 培训PPT生成
│   └── llm.py              # LLM调用封装
└── utils/              # 工具函数（预留）
```

## API清单

### 配置
| 方法 | 端点 | 说明 |
|------|------|------|
| GET | `/api/config` | 读取配置 |
| PUT | `/api/config` | 更新配置 |
| POST | `/api/config/models/validate` | 验证模型连接 |

### 知识库
| 方法 | 端点 | 说明 |
|------|------|------|
| GET | `/api/knowledge-bases` | 列出所有知识库 |
| POST | `/api/knowledge-bases` | 创建知识库 |
| GET | `/api/knowledge-bases/{id}` | 获取知识库详情 |
| DELETE | `/api/knowledge-bases/{id}` | 删除知识库 |

### 文档
| 方法 | 端点 | 说明 |
|------|------|------|
| GET | `/api/knowledge-bases/{id}/documents` | 列出文档 |
| POST | `/api/knowledge-bases/{id}/documents` | 上传文档（支持 PDF、Word、TXT、Markdown，自动解析） |
| GET | `/api/knowledge-bases/{id}/documents/{doc_id}/delete-preview` | 删除预览 |
| DELETE | `/api/knowledge-bases/{id}/documents/{doc_id}` | 删除文档 |

### Wiki
| 方法 | 端点 | 说明 |
|------|------|------|
| GET | `/api/knowledge-bases/{id}/wiki-pages` | 列出Wiki页面 |
| GET | `/api/knowledge-bases/{id}/wiki-pages/{name}` | 获取Wiki内容 |
| POST | `/api/knowledge-bases/{id}/documents/{doc_id}/parse` | 手动解析文档 |

### 对话
| 方法 | 端点 | 说明 |
|------|------|------|
| POST | `/api/chat` | 流式问答（SSE） |
| POST | `/api/chat/sync` | 同步问答 |

### 检索
| 方法 | 端点 | 说明 |
|------|------|------|
| POST | `/api/search` | 原文检索 |

### 培训
| 方法 | 端点 | 说明 |
|------|------|------|
| POST | `/api/training/outline` | 生成PPT大纲 |
| POST | `/api/training/generate` | 生成PPTX文件 |
| GET | `/api/training/download/{filename}` | 下载PPT |

## 启动方式

```bash
# 方式1：使用启动脚本
./start.sh

# 方式2：直接启动
cd /path/to/llm_wiki_safety
python3 -m backend.app

# 方式3：使用uvicorn
cd /path/to/llm_wiki_safety
uvicorn backend.app:app --host 0.0.0.0 --port 8000 --reload
```

## 数据存储

- **配置**: `~/.anniu/config.json`
- **知识库**:
  - 开发态：`./knowledge-bases/`（运行时数据，gitignored）
  - 桌面发布态：`~/.anniu/knowledge-bases/`
- **输出文件**:
  - 开发态：`./output/`（运行时生成物，gitignored）
  - 桌面发布态：`~/.anniu/output/`

### 支持的文档格式

- PDF：仅支持可提取文字的文本版 PDF
- Word：支持 `.docx` 和 `.doc`
- 文本：支持 `.txt` 和 `.md`
- 扫描版 PDF：不支持 OCR 兜底，会直接提示不支持
