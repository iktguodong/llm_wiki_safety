# 安牛产品完整开发实施路线图

**文档版本**: v1.0  
**制定时间**: 2026-05-09  
**有效期**: 2026-05-09 至 2026-06-09（1个月冲刺周期）  
**目标**: 从 Phase 1 (100%) → Phase 2 M2 (完成) + Phase 3 基础

---

## 第一部分：项目全景图

### 整体时间规划

```
Week 1 (5.10-5.16):   P0 阻塞功能突破 - LLM集成 + 文档解析
Week 2 (5.17-5.23):   P0 收尾 + P1 开始 - 关键词检索 + Wiki Lint
Week 3 (5.24-5.30):   P1 继续 - Search高亮 + 配置同步  
Week 4 (5.31-6.06):   P2 启动 - PPT生成基础 + 原文阅读器框架
Week 5 (6.07-6.13):   收尾打磨 - 测试 + 性能优化 + 安全加固
```

### 交付里程碑

| 里程碑 | 时间 | 达成标准 | 提交物 |
|--------|------|---------|--------|
| **M1** | 已达成 | ✅ 知识库/模型配置 | Phase 1 完成 |
| **M2** | 5.30 | ✅ 文档解析/问答/检索流通 | Phase 2 完成 |
| **M3** | 6.13 | ✅ PPT生成可用 | Phase 3 完成 |
| **Beta** | 6.20 | ✅ 完整端到端可用 | 内测版本 |

---

## 第二部分：Week 1 详细计划 (5.10-5.16)

### 🎯 目标

完成 LLM 集成 + 文档解析管道，使"上传文档 → 自动生成 Wiki"流程首次打通。

### 任务分解

#### 任务 1.1: 完成 LLM 服务实现 (2天)

**文件**: `backend/services/llm.py`

**当前状态**: 
```python
class LLMService:
    def __init__(self):
        self.client = httpx.AsyncClient()
    
    async def call(self, messages, model_id, stream=False):
        # ❌ 未实现
        pass
```

**实现要求**:

```python
# 1. 完成 call() 方法 - 支持流式和同步调用
async def call(
    self,
    messages: List[Dict[str, str]], 
    model_id: str,
    stream: bool = False,
    temperature: float = 0.7,
    max_tokens: int = 4096
) -> Union[str, AsyncIterator[str]]:
    """
    调用 LLM API
    
    Args:
        messages: 消息列表 [{"role": "user", "content": "..."}, ...]
        model_id: 模型ID (deepseek-v4-flash 等)
        stream: 是否流式返回
        temperature: 温度参数 (0-1)
        max_tokens: 最大 token 数
        
    Returns:
        stream=False: 完整回复字符串
        stream=True: 异步迭代器，逐个 chunk 返回
        
    Raises:
        ValueError: 找不到模型配置
        HTTPError: API 调用失败
    """
    
    # 步骤1: 从全局 config 找模型配置
    # 步骤2: 获取 base_url + api_key
    # 步骤3: 构建请求体
    # 步骤4: 调用 API
    # 步骤5: 返回/流式返回结果
```

**具体实现步骤**:

```python
# step 1: 连接管理
from backend.config import config

def _get_model_config(self, model_id: str) -> dict:
    """查找模型配置"""
    for provider in config["models"]["providers"]:
        for model in provider["models"]:
            if model["id"] == model_id:
                return {
                    "provider": provider,
                    "model": model
                }
    raise ValueError(f"Model {model_id} not found")

# step 2: 请求体构建
def _build_request(self, messages, model_id, temperature, max_tokens):
    return {
        "model": model_id,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "stream": True  # 始终用流式接收，再转换
    }

# step 3: API 调用（同步模式）
async def call(self, messages, model_id, stream=False, **kwargs):
    config_info = self._get_model_config(model_id)
    provider = config_info["provider"]
    
    if not provider["api_key"]:
        raise ValueError(f"API Key not configured for provider {provider['id']}")
    
    headers = {
        "Authorization": f"Bearer {provider['api_key']}",
        "Content-Type": "application/json"
    }
    
    body = self._build_request(messages, model_id, **kwargs)
    
    url = f"{provider['base_url']}/chat/completions"
    
    async with self.client.stream("POST", url, json=body, headers=headers) as response:
        if response.status_code != 200:
            raise HTTPError(f"API error: {response.status_code}")
        
        if stream:
            return self._stream_response(response)
        else:
            return await self._read_full_response(response)

# step 4: 流式处理
async def _stream_response(self, response):
    """逐行读取流式响应"""
    async for line in response.aiter_lines():
        if line.startswith("data: "):
            data = json.loads(line[6:])
            if "choices" in data and len(data["choices"]) > 0:
                chunk = data["choices"][0].get("delta", {}).get("content", "")
                if chunk:
                    yield chunk

async def _read_full_response(self, response):
    """读取完整响应"""
    full_text = ""
    async for chunk in self._stream_response(response):
        full_text += chunk
    return full_text
```

**验收标准**:
- [ ] ✅ 支持 DeepSeek/OpenAI API 调用
- [ ] ✅ 流式返回可正常解析
- [ ] ✅ 错误处理完整（无 API Key、模型不存在、API 错误）
- [ ] ✅ 手动测试通过（见下方测试脚本）

**测试脚本** (`backend/tests/test_llm.py`):
```python
import asyncio
from backend.services.llm import llm_service
from backend.config import config

async def test_llm():
    # 确保配置有 API Key
    config["models"]["providers"][0]["api_key"] = "your_api_key_here"
    
    messages = [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Hello, who are you?"}
    ]
    
    # 测试同步调用
    print("=== Test 1: Sync Call ===")
    result = await llm_service.call(
        messages, 
        "deepseek-v4-flash",
        stream=False
    )
    print(f"Result: {result[:100]}...")
    
    # 测试流式调用
    print("\n=== Test 2: Stream Call ===")
    async for chunk in await llm_service.call(
        messages,
        "deepseek-v4-flash", 
        stream=True
    ):
        print(chunk, end="", flush=True)
    print("\n✓ LLM service works!")

# 运行: python -m pytest backend/tests/test_llm.py
```

---

#### 任务 1.2: 实现文档解析管道 (3天)

**文件**: `backend/services/wiki.py`

**核心功能**: 上传 PDF/Word → 提取文本 → 调用 LLM 生成 Wiki → 保存

**实现步骤**:

```python
# 步骤 1: 文本提取 (使用 PyPDF + python-docx)
from PyPDF2 import PdfReader
from docx import Document
import markdown

async def _extract_text(self, file_path: str, file_type: str) -> str:
    """
    从文档提取纯文本
    
    Args:
        file_path: 文件绝对路径
        file_type: 文件类型 (pdf/docx/md)
    
    Returns:
        提取的文本 (limit: 50000 chars to avoid token overflow)
    """
    text = ""
    
    if file_type == "pdf":
        with open(file_path, "rb") as f:
            reader = PdfReader(f)
            for page in reader.pages:
                text += page.extract_text() + "\n"
    
    elif file_type == "docx":
        doc = Document(file_path)
        for para in doc.paragraphs:
            text += para.text + "\n"
    
    elif file_type == "md":
        with open(file_path, "r", encoding="utf-8") as f:
            text = f.read()
    
    else:
        raise ValueError(f"Unsupported file type: {file_type}")
    
    # 截断过长内容
    if len(text) > 50000:
        text = text[:50000] + "\n... [内容已截断]"
    
    return text.strip()

# 步骤 2: Wiki 页面生成提示
WIKI_GENERATION_PROMPT = """
你是一个文档解析助手。你需要将以下文档内容解析为结构化的 Wiki 页面。

# 输入文档:
{document_text}

# 任务:
1. 提取主要知识点和章节结构
2. 生成 2-5 个独立的 Wiki 页面，每个页面聚焦一个核心主题
3. 每个页面必须包含:
   - 标题 (title)
   - 简介 (summary, 1-2 句)
   - 完整内容 (content)

# 输出格式 (JSON):
[
  {
    "title": "页面标题",
    "name": "page-slug-name",
    "summary": "一句话概括",
    "content": "# 标题\n\n详细内容...\n\n## 小节\n...",
    "tags": ["标签1", "标签2"]
  },
  ...
]

# 要求:
- 使用 Markdown 格式 content
- name 只能包含英文字母、数字、连字符
- summary 简洁清晰
- 确保输出是有效的 JSON 数组
"""

# 步骤 3: 调用 LLM 生成 Wiki
async def _generate_wiki_pages(
    self, 
    doc_text: str,
    model_id: str = None
) -> List[Dict]:
    """
    调用 LLM 生成 Wiki 页面
    
    Returns:
        [
            {
                "title": "...",
                "name": "...",
                "summary": "...",
                "content": "...",
                "tags": [...]
            },
            ...
        ]
    """
    from backend.services.llm import llm_service
    
    # 使用默认模型或指定模型
    if not model_id:
        model_id = config["current_model_id"]
    
    prompt = WIKI_GENERATION_PROMPT.format(document_text=doc_text)
    
    messages = [
        {
            "role": "system",
            "content": "You are a knowledge extraction assistant. Output valid JSON only."
        },
        {
            "role": "user",
            "content": prompt
        }
    ]
    
    # 调用 LLM（非流式）
    response = await llm_service.call(
        messages,
        model_id,
        stream=False,
        temperature=0.3,  # 降低温度保证格式
        max_tokens=8000
    )
    
    # 解析 JSON
    try:
        # 可能包含 markdown code block，需要提取
        if "```json" in response:
            response = response.split("```json")[1].split("```")[0]
        elif "```" in response:
            response = response.split("```")[1].split("```")[0]
        
        pages = json.loads(response)
        return pages
    except json.JSONDecodeError as e:
        raise ValueError(f"LLM returned invalid JSON: {str(e)}")

# 步骤 4: 保存 Wiki 页面到磁盘
async def _save_wiki_pages(
    self,
    kb_id: str,
    pages: List[Dict],
    source_doc_id: str
) -> List[str]:
    """
    保存 Wiki 页面到 wiki/ 目录
    
    Returns:
        保存的页面文件名列表
    """
    from backend.config import get_kb_wiki_path, get_kb_doc_track_path
    import datetime
    
    wiki_dir = get_kb_wiki_path(kb_id)
    wiki_dir.mkdir(parents=True, exist_ok=True)
    
    saved_pages = []
    
    for page in pages:
        # 生成文件名
        filename = f"{page['name']}.md"
        filepath = wiki_dir / filename
        
        # 构建 Markdown 内容 (含 frontmatter)
        content = f"""---
title: {page['title']}
summary: {page['summary']}
tags: {json.dumps(page['tags'])}
last_updated: {datetime.datetime.now().isoformat()}
sources: ["{source_doc_id}"]
---

{page['content']}
"""
        
        # 写入文件
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)
        
        saved_pages.append(filename)
    
    return saved_pages

# 步骤 5: 更新文档追踪 (文档 ↔ Wiki 映射)
async def _update_doc_track(
    self,
    kb_id: str,
    doc_id: str,
    doc_filename: str,
    wiki_pages: List[str]
):
    """
    更新 raw/文档追踪.json，记录文档与 Wiki 关系
    """
    from backend.config import get_kb_doc_track_path
    
    track_file = get_kb_doc_track_path(kb_id)
    track_file.parent.mkdir(parents=True, exist_ok=True)
    
    # 读取现有追踪
    tracking = {}
    if track_file.exists():
        with open(track_file, "r", encoding="utf-8") as f:
            tracking = json.load(f)
    
    # 添加新的映射
    tracking["documents"] = tracking.get("documents", {})
    tracking["documents"][doc_id] = {
        "file": doc_filename,
        "uploaded_at": datetime.datetime.now().isoformat(),
        "wiki_pages": [f"wiki/{page}" for page in wiki_pages]
    }
    
    # 保存
    with open(track_file, "w", encoding="utf-8") as f:
        json.dump(tracking, f, ensure_ascii=False, indent=2)

# 步骤 6: 主流程 - parse_document()
async def parse_document(
    self,
    kb_id: str,
    doc_id: str,
    model_id: str = None
) -> bool:
    """
    完整的文档解析流程
    
    Returns:
        成功返回 True，失败返回 False
    """
    from backend.config import get_kb_raw_path, get_kb_path, get_kb_meta_path
    
    try:
        # 1. 获取文档信息
        doc_meta = await doc_service.get_document(kb_id, doc_id)
        if not doc_meta:
            raise ValueError("Document not found")
        
        # 2. 构建文件路径
        raw_dir = get_kb_raw_path(kb_id)
        doc_path = raw_dir / doc_meta["file"]
        
        if not doc_path.exists():
            raise FileNotFoundError(f"Document file not found: {doc_path}")
        
        # 3. 检测文件类型
        file_ext = doc_path.suffix.lower()
        file_type_map = {".pdf": "pdf", ".docx": "docx", ".md": "md"}
        file_type = file_type_map.get(file_ext)
        
        if not file_type:
            raise ValueError(f"Unsupported file type: {file_ext}")
        
        # 4. 提取文本
        print(f"[parse] Extracting text from {doc_meta['file']}...")
        doc_text = await self._extract_text(str(doc_path), file_type)
        
        # 5. 生成 Wiki 页面
        print(f"[parse] Generating Wiki pages using LLM...")
        wiki_pages = await self._generate_wiki_pages(doc_text, model_id)
        
        # 6. 保存 Wiki 页面
        print(f"[parse] Saving {len(wiki_pages)} Wiki pages...")
        saved_pages = await self._save_wiki_pages(kb_id, wiki_pages, doc_id)
        
        # 7. 更新文档追踪
        await self._update_doc_track(kb_id, doc_id, doc_meta["file"], saved_pages)
        
        # 8. 更新知识库元数据
        kb_meta_path = get_kb_meta_path(kb_id)
        kb_meta = {}
        if kb_meta_path.exists():
            with open(kb_meta_path, "r", encoding="utf-8") as f:
                kb_meta = json.load(f)
        
        kb_meta["statistics"] = kb_meta.get("statistics", {})
        kb_meta["statistics"]["wiki_page_count"] = len(saved_pages)
        kb_meta["updated_at"] = datetime.datetime.now().isoformat()
        
        with open(kb_meta_path, "w", encoding="utf-8") as f:
            json.dump(kb_meta, f, ensure_ascii=False, indent=2)
        
        print(f"[parse] ✓ Document {doc_id} parsed successfully!")
        return True
    
    except Exception as e:
        print(f"[parse] ✗ Error parsing document: {str(e)}")
        return False
```

**验收标准**:
- [ ] ✅ 支持 PDF/Word/Markdown 解析
- [ ] ✅ LLM 生成有效的 Wiki 页面结构
- [ ] ✅ Wiki 页面正确保存到 wiki/ 目录
- [ ] ✅ 文档追踪.json 正确更新
- [ ] ✅ meta.json 页数统计正确
- [ ] ✅ 错误处理完整（文件不存在、LLM 失败等）

**端到端测试** (`backend/tests/test_parse.py`):
```python
async def test_parse_document():
    # 1. 创建测试知识库
    kb = await kb_service.create({"name": "Test KB"})
    kb_id = kb.id
    
    # 2. 上传测试文件
    test_file = Path("tests/fixtures/sample.pdf")
    doc = await doc_service.upload(kb_id, "sample.pdf", test_file.read_bytes())
    
    # 3. 解析文档
    result = await wiki_service.parse_document(kb_id, doc.id)
    
    # 4. 验证
    assert result == True
    
    # 5. 检查 Wiki 页面是否生成
    wiki_dir = get_kb_wiki_path(kb_id)
    wiki_files = list(wiki_dir.glob("*.md"))
    assert len(wiki_files) > 0
    print(f"✓ Generated {len(wiki_files)} Wiki pages")
    
    # 6. 检查文档追踪
    track_file = get_kb_doc_track_path(kb_id)
    assert track_file.exists()
    with open(track_file) as f:
        track_data = json.load(f)
    assert doc.id in track_data["documents"]
    print(f"✓ Document tracking updated")
```

---

#### 任务 1.3: 前端自动解析触发 (1天)

**文件**: `frontend/src/app/components/pages/KnowledgeBasePage.tsx`

**当前问题**: 文档上传后没有触发解析

**修复**:
```typescript
// 在 handleUpload 方法中添加解析触发
const handleUpload = async (kbId: string, file: File) => {
  setUploading(true);
  try {
    // 上传文档
    const doc = await docApi.upload(kbId, file);
    
    // ✨ 新增: 触发后端解析
    try {
      await wikiApi.parse(kbId, doc.id);
      setUploadGuides(prev => ({ ...prev, [kbId]: true }));
    } catch (err) {
      // 解析可以失败不影响上传成功
      console.warn("Document parse failed:", err);
    }
    
    await loadDocs(kbId);
    await refreshKbs();
  } catch (err) {
    alert("Upload failed: " + (err instanceof Error ? err.message : "Unknown error"));
  } finally {
    setUploading(false);
  }
};
```

**验收标准**:
- [ ] ✅ 上传后自动触发解析 API
- [ ] ✅ 显示解析进度提示
- [ ] ✅ 解析失败不影响上传结果

---

### 📊 Week 1 验收标准

```
✓ LLM 服务完整可用 (流式 + 同步)
✓ 文档解析管道打通 (PDF/Word/MD → Wiki)
✓ Wiki 页面正确保存和追踪
✓ 前端自动触发解析
✓ 手动测试通过 (至少 1 个完整流程)
→ 能演示: 上传文件 → 看到 Wiki 页面生成
```

---

## 第三部分：Week 2 详细计划 (5.17-5.23)

### 🎯 目标

完成关键词检索 + Wiki Lint，使知识问答和质量检查功能首次可用。

### 任务分解

#### 任务 2.1: 关键词检索实现 (2天)

**文件**: `backend/services/chat.py`

**实现**:

```python
# 当前缺失的 _find_related_pages() 方法

async def _find_related_pages(
    self,
    question: str,
    kb_ids: List[str],
    max_pages: int = 5
) -> List[Dict]:
    """
    根据问题找到相关的 Wiki 页面
    
    策略: 关键词匹配 + 简易相似度计算
    
    Returns:
        [
            {
                "name": "port-fire-emergency",
                "title": "港口火灾应急",
                "score": 0.85  # 相关度分数
            },
            ...
        ]
    """
    from collections import Counter
    import re
    from backend.config import get_kb_wiki_path
    
    related_pages = []
    
    # 步骤1: 分词问题
    question_words = self._tokenize(question)
    question_set = set(question_words)
    
    # 步骤2: 遍历所有知识库的 Wiki 页面
    for kb_id in kb_ids:
        wiki_dir = get_kb_wiki_path(kb_id)
        if not wiki_dir.exists():
            continue
        
        # 遍历所有 .md 文件
        for wiki_file in wiki_dir.glob("*.md"):
            if wiki_file.name in ["index.md", "log.md"]:
                continue  # 跳过系统页面
            
            # 读取页面内容
            with open(wiki_file, "r", encoding="utf-8") as f:
                content = f.read()
            
            # 分词
            page_words = self._tokenize(content)
            page_set = set(page_words)
            
            # 计算相似度 (Jaccard 相似度)
            intersection = len(question_set & page_set)
            if intersection > 0:
                union = len(question_set | page_set)
                score = intersection / union if union > 0 else 0
                
                # 提取页面标题
                title_match = re.search(r"title:\s*(.+)", content)
                title = title_match.group(1) if title_match else wiki_file.stem
                
                related_pages.append({
                    "name": wiki_file.stem,
                    "title": title,
                    "score": score,
                    "kb_id": kb_id
                })
    
    # 步骤3: 排序并返回 top-k
    related_pages.sort(key=lambda x: x["score"], reverse=True)
    return related_pages[:max_pages]

def _tokenize(self, text: str) -> List[str]:
    """
    简单分词 (中文使用 jieba，英文使用空格)
    """
    import re
    
    # 移除标点和特殊字符
    text = re.sub(r"[^\w\s]", " ", text, flags=re.UNICODE)
    
    # 简单分词 (实际项目应使用 jieba/spacy)
    words = text.lower().split()
    
    # 过滤停用词
    stopwords = {"the", "a", "an", "and", "or", "is", "are", "of", "in"}
    words = [w for w in words if w not in stopwords and len(w) > 1]
    
    return words

# 在 ask() 中调用
async def ask(
    self,
    question: str,
    kb_ids: List[str],
    model_id: str = None
):
    """知识问答"""
    from backend.services.llm import llm_service
    
    # 1. 找相关页面
    related_pages = await self._find_related_pages(question, kb_ids, max_pages=5)
    
    if not related_pages:
        yield "暂无相关知识库内容。"
        return
    
    # 2. 读取相关页面内容
    context = ""
    for page in related_pages:
        wiki_path = get_kb_wiki_path(page["kb_id"]) / f"{page['name']}.md"
        if wiki_path.exists():
            with open(wiki_path, "r", encoding="utf-8") as f:
                context += f"## {page['title']}\n{f.read()}\n\n"
    
    # 3. 组装 prompt
    system_prompt = """你是一个知识库问答助手。
根据以下知识库内容回答用户问题。
如果知识库中没有相关信息，请说明。
"""
    
    user_prompt = f"""基于以下知识库内容，回答问题:

【知识库内容】
{context}

【用户问题】
{question}

请提供详细的答案。
"""
    
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt}
    ]
    
    # 4. 调用 LLM (流式)
    if not model_id:
        model_id = config["current_model_id"]
    
    async for chunk in await llm_service.call(
        messages,
        model_id,
        stream=True
    ):
        yield chunk
```

**验收标准**:
- [ ] ✅ 找到相关 Wiki 页面
- [ ] ✅ 相似度计算正确
- [ ] ✅ 流式返回 LLM 答案
- [ ] ✅ 测试多个知识库时正确

---

#### 任务 2.2: Wiki 质量检查 (Lint) 实现 (2天)

**文件**: `backend/services/wiki.py`

**实现**:

```python
async def lint_wiki(self, kb_id: str) -> Dict:
    """
    检查 Wiki 质量问题
    
    Returns:
        {
            "total_pages": 10,
            "issues": [
                {
                    "type": "broken_link",
                    "severity": "error",
                    "page": "port-fire",
                    "message": "链接 [[missing-page]] 页面不存在"
                },
                ...
            ],
            "summary": "发现 3 个错误，2 个警告"
        }
    """
    from backend.config import get_kb_wiki_path
    import re
    
    wiki_dir = get_kb_wiki_path(kb_id)
    issues = []
    
    # 1. 扫描所有页面
    all_wiki_files = set(
        f.stem for f in wiki_dir.glob("*.md") if f.name not in ["index.md", "log.md"]
    )
    
    # 2. 检查每个页面
    for wiki_file in wiki_dir.glob("*.md"):
        if wiki_file.name in ["index.md", "log.md"]:
            continue
        
        page_name = wiki_file.stem
        
        with open(wiki_file, "r", encoding="utf-8") as f:
            content = f.read()
        
        # 检查 1: 格式检查 (frontmatter)
        if not content.startswith("---"):
            issues.append({
                "type": "format",
                "severity": "error",
                "page": page_name,
                "message": "缺少 frontmatter (YAML front matter)"
            })
        
        # 检查 2: 断链检测
        links = re.findall(r"\[\[([^\]]+)\]\]", content)
        for link in links:
            link_target = link.split("|")[0].strip()
            if link_target not in all_wiki_files:
                issues.append({
                    "type": "broken_link",
                    "severity": "error",
                    "page": page_name,
                    "message": f"断链: [[{link_target}]] 页面不存在",
                    "suggestion": f"该链接指向的页面不存在，请检查拼写或删除链接"
                })
        
        # 检查 3: 标题检查
        if not re.search(r"^# ", content, re.MULTILINE):
            issues.append({
                "type": "format",
                "severity": "warning",
                "page": page_name,
                "message": "缺少一级标题 (#)"
            })
        
        # 检查 4: 来源检查 (sources 字段)
        sources_match = re.search(r'sources:\s*\[([^\]]*)\]', content)
        if not sources_match or not sources_match.group(1).strip():
            issues.append({
                "type": "missing_source",
                "severity": "warning",
                "page": page_name,
                "message": "缺少来源声明 (sources 字段为空)",
                "suggestion": "在 frontmatter 中添加 sources 字段，记录该页面来自哪个文档"
            })
    
    # 规范3: 孤儿页判定 (被文档引用但在索引中未被引用)
    # 这需要读取 index.md 看有哪些页面被明确组织
    index_file = wiki_dir / "index.md"
    if index_file.exists():
        with open(index_file, "r", encoding="utf-8") as f:
            index_content = f.read()
        
        referenced_pages = set(re.findall(r"\[\[([^\]]+)\]\]", index_content))
        orphan_pages = all_wiki_files - referenced_pages
        
        for orphan_page in orphan_pages:
            issues.append({
                "type": "orphan",
                "severity": "info",
                "page": orphan_page,
                "message": "孤儿页面：未在 index 中对应引用",
                "suggestion": "可考虑在 index.md 中添加对该页面的引用"
            })
    
    # 统计
    error_count = len([i for i in issues if i["severity"] == "error"])
    warning_count = len([i for i in issues if i["severity"] == "warning"])
    info_count = len([i for i in issues if i["severity"] == "info"])
    
    summary = f"发现 {error_count} 个错误，{warning_count} 个警告，{info_count} 条提示"
    
    return {
        "total_pages": len(all_wiki_files),
        "issues": issues,
        "summary": summary
    }
```

**验收标准**:
- [ ] ✅ 检测格式问题（缺少 frontmatter）
- [ ] ✅ 检测断链（链接目标不存在）
- [ ] ✅ 检测孤儿页（未在 index 中引用）
- [ ] ✅ 检测缺失来源（sources 为空）
- [ ] ✅ 问题分级正确（error/warning/info）

---

#### 任务 2.3: 前端 Lint 展示优化 (1天)

**文件**: `frontend/src/app/components/pages/KnowledgeBasePage.tsx`

**当前问题**: Lint 结果展示不完整

**改进**: 已在第一部分修复中完成（支持按严重程度分颜色展示）

---

### 📊 Week 2 验收标准

```
✓ 关键词检索正确找到相关页面
✓ 知识问答能流式返回 LLM 答案
✓ Wiki Lint 检查所有类型问题
✓ 前端正确展示 Lint 结果
→ 能演示: 提问 → 得到相关内容的答案
```

---

## 第四部分：Week 3-4 计划概览

### Week 3 (5.24-5.30): P1 收尾

#### 任务 3.1: 搜索高亮与分组
- **文件**: `backend/services/search.py` + `frontend/src/app/components/pages/SearchPage.tsx`
- **目标**: 搜索结果按知识库分组，关键词高亮显示
- **工作量**: 2-3天

#### 任务 3.2: 配置同步机制
- **文件**: `frontend/src/lib/context.tsx` + `backend/config.py`
- **目标**: 知识库/模型切换实时同步全局状态
- **工作量**: 1-2天

### Week 4 (5.31-6.06): P2 启动

#### 任务 4.1: PPT 生成基础
- **文件**: `backend/services/training.py`
- **目标**: 根据 Wiki 内容生成 PPT 大纲
- **工作量**: 3-4天

#### 任务 4.2: 原文阅读器框架
- **文件**: `frontend/src/app/components/pages/ReaderPage.tsx` (新建)
- **目标**: PDF 翻页+高亮基础框架
- **工作量**: 2-3天

---

## 第五部分：测试与验收

### 单元测试 (每个任务完成后)

```bash
# LLM 服务
pytest backend/tests/test_llm.py -v

# 文档解析
pytest backend/tests/test_parse.py -v

# 关键词检索
pytest backend/tests/test_search.py -v

# Lint 功能
pytest backend/tests/test_lint.py -v
```

### 集成测试 (每个 Week 完成后)

```bash
# 完整的知识库工作流
pytest backend/tests/test_workflow.py -v

# API 端到端测试
pytest backend/tests/test_api_integration.py -v

# 前端交互测试
npm run test:e2e
```

### 手动验收清单

#### Week 1 手动验收
```
□ 设置 API Key → DeepSeek/OpenAI 连接成功
□ 上传 PDF 文件 → 自动生成 3+ 个 Wiki 页面
□ 检查 wiki/ 目录→ 页面文件存在
□ 检查 meta.json → 页数统计正确
□ Ctrl+Enter 发送消息 → 无错误
```

#### Week 2 手动验收
```
□ 知识库页面点击"检查Wiki" → Lint 结果展示正确
□ Chat 页面输入问题 → 收到 LLM 流式回复
□ 回复包含 [[页面引用]] → 格式正确
□ Search 页面搜索关键词 → 结果按知识库分组
```

---

## 第六部分：依赖与风险

### 外部依赖

| 依赖 | 版本 | 原因 |
|------|------|------|
| PyPDF2 | >=3.0 | PDF 文本提取 |
| python-docx | >=0.8.11 | Word 文档处理 |
| python-pptx | >=0.6 | PPT 生成 (Week 4) |
| jieba | >=0.42.1 | 中文分词 (可选，当前用简单分词) |

**安装**:
```bash
pip install PyPDF2 python-docx python-pptx jieba
# 更新 requirements.txt
```

### 技术风险

| 风险 | 缓解方案 |
|------|---------|
| LLM API 调用延迟 | 添加 timeout + 重试机制；提供进度提示 |
| 大文件解析 (>50MB) | 文本截断到 50k chars；分页处理 |
| 中文分词准确度 | 先用简单分词，后换 jieba |
| 并发写入 config.json | 添加文件锁保护 |

---

## 第七部分：交付物清单

### 每个 Week 交付

#### Week 1 交付物
- [ ] `backend/services/llm.py` - 完整实现
- [ ] `backend/services/wiki.py` - parse_document() 完整
- [ ] `backend/tests/test_llm.py` - LLM 测试
- [ ] `backend/tests/test_parse.py` - 解析测试
- [ ] 测试数据文件: `tests/fixtures/sample.pdf`
- [ ] 验收记录: 完整的手动测试截图

#### Week 2 交付物
- [ ] `backend/services/chat.py` - _find_related_pages() 完整
- [ ] `backend/services/wiki.py` - lint_wiki() 完整
- [ ] `backend/tests/test_search.py`
- [ ] `backend/tests/test_lint.py`
- [ ] 验收记录

#### Week 3-4 交付物
- [ ] `backend/services/training.py` + `search.py` 完整
- [ ] `frontend/src/app/components/pages/ReaderPage.tsx`
- [ ] E2E 测试脚本
- [ ] 完整的产品演示视频 (5-10 分钟)

---

## 第八部分：质量保证

### 代码规范

所有新代码需满足:
- [ ] 类型注解完整 (Python: type hints; TypeScript: strict mode)
- [ ] docstring/注释清晰
- [ ] 错误处理完善（try/except + 日志）
- [ ] 单元测试覆盖率 >70%

### 性能基准

| 操作 | 目标耗时 |
|------|---------|
| 文档解析 (10MB PDF) | <30s |
| 关键词检索 (100 页 Wiki) | <500ms |
| LLM 流式调用首字节 | <3s |
| Wiki Lint (100 页) | <2s |

### 监控与日志

所有关键函数添加日志:
```python
import logging

logger = logging.getLogger(__name__)

# 使用示例
logger.info(f"[wiki] Starting to parse document {doc_id}")
logger.error(f"[llm] API error: {e}", exc_info=True)
```

---

## 第九部分：团队分工建议（如果多人）

如果是团队开发，建议分工：

| 人员 | 任务 | 时间 |
|------|------|------|
| 后端 A | LLM 服务 + 文档解析 | Week 1 |
| 后端 B | 关键词检索 + Wiki Lint | Week 2 |
| 前端 A | KnowledgeBasePage 优化 + ChatPage 修复 | Week 1-2 |
| 前端 B | SearchPage + 原文阅读器 | Week 3-4 |
| 测试/运维 | 测试脚本 + CI/CD | 持续 |

---

## 最终检查清单

在提交到生产（Beta）前，确认:

- [ ] ✅ 所有 Week 1-2 任务 100% 完成
- [ ] ✅ 无 blocking bug (critical priority bugs = 0)
- [ ] ✅ 完整的端到端工作流可演示
- [ ] ✅ 核心 API 响应时间 <5s
- [ ] ✅ 错误处理完善，前端可见错误消息
- [ ] ✅ 多用户/多知识库测试通过
- [ ] ✅ 安全检查完成 (API Key 不泄露等)
- [ ] ✅ 文档更新日期 = 交付日期

---

**总体估算**: 
- **开发**: 5-7 个工作日 (如按计划执行)
- **测试**: 2-3 个工作日
- **微调**: 1-2 个工作日
- **总时间**: 2-3 周可达到 Phase 2 M2 + Beta 就绪

**关键成功因素**:
1. LLM 集成必须在 Day 1-2 完成
2. 文档解析必须在 Day 3-5 完成（这是核心）
3. Week 2 必须完成检索+问答闭环
4. 每个任务完成后立即测试，不要等到最后

