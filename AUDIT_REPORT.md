# 安牛代码库审计报告

**审计时间**: 2026-05-09  
**审计范围**: 全仓库代码检查  
**审计员**: 资深全栈代码审计专家

---

## 一、整体评估

- **项目健康度评分**：4.5/10
- **核心风险概览**：
  - 🔴 **前后端契约严重不一致**：ApiResponse 结构完全不匹配，所有 API 请求不可用
  - 🔴 **CORS 中间件缺失**：浏览器跨域请求被拦截，前端无法通信
  - 🔴 **数据字段映射错误**：多个模型字段名/类型不一致导致数据解析失败
  - 🟡 **异步流程管理混乱**：ChatPage 中 loading 状态管理有缺陷
  - 🟡 **API 参数设计不规范**：training/outline 端点混用 query 和 body

---

## 二、问题清单（按严重程度分级）

### 🔴 严重（Blocker，影响功能可用）

| # | 文件:行号 | 问题描述 | 修复建议 |
|---|----------|---------|---------|
| 1 | frontend/src/lib/types.ts:6-10 vs backend/models.py:13-17 | **ApiResponse 结构完全不匹配** - 后端返回 `{success, message, data}`，前端期望 `{code, message, data}`；前端 api.ts:43 检查 `data.code !== 200` 会永远失败 | 统一使用一套结构。建议后端改为: `code: int = 200, message: str = "", data: Optional[Any] = None`。或前端改为检查 `!data.success` |
| 2 | backend/app.py:40-44 | **缺失 CORS 中间件** - FastAPI 未配置 CORSMiddleware，前端 http://localhost:5173 访问 http://localhost:8000 被浏览器拦截 | 在 app 创建后添加: `from fastapi.middleware.cors import CORSMiddleware; app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173", "http://localhost:3000"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])` |
| 3 | frontend/src/lib/types.ts:21 vs backend/models.py:72 | **KnowledgeBase.size 类型错误** - 后端返回 `total_size_mb: float`，前端定义为 `size: string`；KnowledgeBasePage.tsx:155 直接显示导致不一致 | 统一类型：前端改为 `total_size_mb: number` 或后端改为 `size: str = "0 MB"` |
| 4 | frontend/src/lib/types.ts:35-43 vs backend/models.py:83-91 | **DocumentInfo 字段全量不匹配** - 后端有 `file_size_mb`, `page_count`, `wiki_pages: List[str]`, `parse_status`；前端期望 `size: number`, `pages?: number`, `wiki_pages?: number` (类型错误), `status` | 前端改为完全匹配后端字段名和类型：`file, file_size_mb, page_count, wiki_pages: string[], parse_status` |
| 5 | frontend/src/app/components/pages/ChatPage.tsx:56-91 | **异步流状态管理缺陷** - line 90 的 `setIsLoading(false)` 在流式开始前同步执行，导致 loading 状态立即变为 false，即使 stream 还在进行；while 循环继续时按钮可再次点击导致重复请求 | (1) 删除 line 90；(2) 使用 AbortController 防止重复；(3) 改为 async/await 而非回调 |
| 6 | frontend/src/lib/api.ts:43 | **API 响应校验逻辑错误** - 检查 `data.code !== 200` 但后端不返回 code 字段，导致所有请求都进入异常分支 | 改为检查 success 字段或统一后端返回 code |
| 7 | backend/app.py:166-172 | **wikip 页面路径遍历漏洞** - `page_name` 参数直接拼接进文件路径（line 328），未验证是否包含 `..` 导致可路径遍历：`GET /wiki-pages/../../../../etc/passwd` | 在 get_wiki_page 返回前校验：`if ".." in page_name or page_name.startswith("/"): raise HTTPException(status_code=400)` |
| 8 | frontend/src/lib/types.ts:57-62 vs backend/models.py:116-123 | **WikiPage 字段缺失** - 后端有 `summary`, `last_updated`, `sources: List[str]`；前端缺少 summary，sources，last_updated；多了 `source_doc`, `created_at` | 前端改为：`summary: string; last_updated: string; sources: string[]` (移除 source_doc, created_at) |

### 🟡 警告（Major，影响稳定性/契约）

| # | 文件:行号 | 问题描述 | 修复建议 |
|---|----------|---------|---------|
| 9 | backend/app.py:228-233 | **API 端点参数位置混乱** - `/api/training/outline` 期望 query 参数 `source_type`, `source_ids`, `config`，但将 TrainingConfig 对象作为 query 参数不合法；应改为 POST body | 改为 `TrainingOutlineRequest` 模型（类似 line 224），统一在 body 中传递 |
| 10 | frontend/src/app/components/pages/ChatPage.tsx:68-89 | **流式 API 调用无 await 导致 Promise 未捕获** - chatApi.ask 返回 Promise 但未 await，如发生错误可能导致未捕获异常 | 改为 `await chatApi.ask(...)` 或使用 `.catch()` 链 |
| 11 | frontend/src/lib/api.ts:124-142 | **流式处理没有取消机制** - onChunk 可能在组件卸载后调用，导致内存泄漏和警告；无法中途中断请求 | 返回 AbortController，支持取消：`return { cancel: () => controller.abort(), promise: ... }` |
| 12 | backend/config.py:70-74 | **并发写入配置无保护** - 多个请求同时调用 `save_config()` 时，JSON 文件可能被部分覆盖 | 使用 `threading.Lock()` 保护配置文件写入 |
| 13 | backend/services/wiki.py:134-145 | **文件打开未使用 context manager** - 直接 open()、JSON load 可能 raise，没有 try/except 保护 | 改为 `try/except` 块或确保 `raw_path` 存在后再读 |
| 14 | backend/services/chat.py:87-88 | **同上** - 文件读取无异常处理 | 添加 try/except |
| 15 | frontend/src/lib/api.ts:97-100 | **删除文档参数位置错误** - 通过 query string 传递 `delete_wiki`，但后端 app.py:147 定义为 path 参数；应改为 DELETE body 或改端点 | 改为 `DELETE /api/knowledge-bases/{kb_id}/documents/{doc_id}` + body: `{delete_wiki_pages: boolean}` |
| 16 | backend/app.py:203 | **流式响应无超时保护** - StreamingResponse 无 timeout 和错误恢复机制 | 在 generate() 中添加 timeout 和错误处理 |
| 17 | backend/services/wiki.py:162-164 | **AGENTS.md 仅在 wiki 解析时使用** - 但 chat.py (问答) 和 training.py (培训) 都没有使用该规范，不一致 | 在 chat.py 和 training.py 的 LLM 调用处也注入 AGENTS.md system prompt |
| 18 | backend/services/wiki.py:177 | **JSON 解析无验证** - `json.loads(json_match.group())` 可能失败，虽然有 except 但应在异常时记录日志 | 添加 logger 记录 JSON 解析失败的内容 |
| 19 | backend/app.py:131-132 | **asyncio.create_task 无 task 引用** - fire-and-forget 任务可能被垃圾回收，导致文档解析不执行 | 保存 task 引用或使用任务队列 (celery/rq) |

### 🔵 提示（Minor，代码质量优化）

| # | 文件:行号 | 问题描述 | 修复建议 |
|---|----------|---------|---------|
| 20 | backend/services/llm.py:16 | **全局 httpx 客户端从不关闭** - `self.client` 在应用退出时未关闭，可能导致资源泄漏 | 添加应用关闭钩子：`app.add_event_handler("shutdown", llm_service.close)` |
| 21 | frontend/src/lib/context.tsx:32-48 | **refreshKbs 在每次 render 时都 invalidate** - 虽然有 useCallback，但依赖为空，可能导致频繁重新获取 | 如无必要不频繁刷新，或增加缓存策略 |
| 22 | backend/app.py:284 | **日志级别写死为 info** - 调试时应支持 DEBUG 模式 | 改为 `log_level=os.getenv("LOG_LEVEL", "info")` |
| 23 | backend/models.py:51-52 | **AppConfig 中 models 和 knowledge_bases 类型为 Dict[str, Any]** - 应使用具体类型 Pydantic 模型以获得完整的类型检查 | 创建 `ModelsConfig` 和 `KnowledgeBasesConfig` 模型 |
| 24 | frontend/src/app/components/pages/ChatPage.tsx:93 | **allModels 在每次 render 计算** - 应 memoize | 改为 `const allModels = useMemo(() => providers.flatMap(...), [providers])` |
| 25 | backend/services/search.py:72-103 | **搜索速度可优化** - 逐字符逐文件搜索，大文档会 slow；应预构建索引 | 考虑集成 Whoosh 或 Elasticsearch |

---

## 三、前后端契约对照表

| 字段 | 后端 (models.py) | 前端 (types.ts) | 备注 | 一致 |
|------|-----------------|----------------|------|------|
| **ApiResponse** | | | | |
| code | ❌ 无 | ✅ `code: number` | 最严重的不匹配 | ❌ |
| success | ✅ `success: bool` | ❌ 无 | 后端有前端没有 | ❌ |
| message | ✅ `message: str` | ✅ `message: string` | ✅ 一致 | ✅ |
| data | ✅ `Optional[Any]` | ✅ `T` (generic) | ✅ 一致 | ✅ |
| **KnowledgeBase** | | | | |
| id | ✅ `str` | ✅ `string` | ✅ 一致 | ✅ |
| name | ✅ `str` | ✅ `string` | ✅ 一致 | ✅ |
| description | ✅ `str` | ✅ `string?` | ✅ 一致 | ✅ |
| created_at | ✅ `str` | ✅ `string` | ✅ 一致 | ✅ |
| updated_at | ✅ `str` | ✅ `string` | ✅ 一致 | ✅ |
| document_count | ✅ `int` | ✅ `number` | ✅ 一致 | ✅ |
| wiki_page_count | ✅ `int` | ✅ `number` | ✅ 一致 | ✅ |
| total_size_mb | ✅ `float` | ❌ `size: string` | 名称和类型都错 | ❌ |
| **DocumentInfo** | | | | |
| id | ✅ `str` | ✅ `string` | ✅ 一致 | ✅ |
| file | ✅ `str` | ❌ `filename` | 名称错误 | ❌ |
| file_size_mb | ✅ `float` | ❌ `size: number` (但名称错) | 名称错误 | ❌ |
| page_count | ✅ `int` | ❌ `pages?: number` | 名称错误 | ❌ |
| wiki_pages | ✅ `List[str]` | ❌ `wiki_pages?: number` | 类型完全错误 | ❌ |
| parse_status | ✅ `str` | ❌ `status` | 名称错误 | ❌ |
| uploaded_at | ✅ `str` | ✅ `string` | ✅ 一致 | ✅ |
| **WikiPage** | | | | |
| name | ✅ `str` | ✅ `string` | ✅ 一致 | ✅ |
| title | ✅ `str` | ✅ `string` | ✅ 一致 | ✅ |
| summary | ✅ `str` | ❌ 无 | 前端缺少此字段 | ❌ |
| last_updated | ✅ `str` | ❌ `created_at` | 名称和语义都错 | ❌ |
| sources | ✅ `List[str]` | ❌ `source_doc: string` | 类型和名称都错 | ❌ |
| **其他模型** | | | | |
| 总体一致率 | — | — | — | ⚠️ <40% |

---

## 四、API 端点对照表

| 后端路由 | 前端调用 | URL | 请求体 | 状态 |
|---------|---------|-----|--------|------|
| **知识库** | | | | |
| GET /api/knowledge-bases | kbApi.list() | ✅ 正确 | — | ⚠️ 契约不匹配 |
| POST /api/knowledge-bases | kbApi.create() | ✅ 正确 | ✅ 正确 | ⚠️ 契约不匹配 |
| GET /api/knowledge-bases/{kb_id} | kbApi.get() | ✅ 正确 | — | ⚠️ 契约不匹配 |
| DELETE /api/knowledge-bases/{kb_id} | kbApi.delete() | ✅ 正确 | — | ⚠️ 契约不匹配 |
| **文档** | | | | |
| GET /api/knowledge-bases/{kb_id}/documents | docApi.list() | ✅ 正确 | — | ⚠️ 契约不匹配 |
| POST /api/knowledge-bases/{kb_id}/documents | docApi.upload() | ✅ 正确 | FormData ✅ | ⚠️ 契约不匹配 |
| DELETE /api/knowledge-bases/{kb_id}/documents/{doc_id} | docApi.delete() | ✅ 正确 | ❌ Query 参数错 | ❌ 参数位置错 |
| GET .../delete-preview | docApi.deletePreview() | ✅ 正确 | — | ⚠️ 契约不匹配 |
| **Wiki** | | | | |
| GET /api/knowledge-bases/{kb_id}/wiki-pages | wikiApi.list() | ✅ 正确 | — | ⚠️ 契约不匹配 |
| GET .../wiki-pages/{page_name} | wikiApi.get() | ⚠️ 无防护 | — | ❌ 路径遍历漏洞 |
| POST .../documents/{doc_id}/parse | wikiApi.parse() | ✅ 正确 | — | ⚠️ 契约不匹配 |
| POST /api/knowledge-bases/{kb_id}/wiki-lint | wikiApi.lint() | ✅ 正确 | — | ⚠️ 契约不匹配 |
| **对话** | | | | |
| POST /api/chat | chatApi.ask() | ✅ 正确 | ✅ 正确 | ❌ 流式处理缺缺陷 |
| POST /api/chat/sync | chatApi.askSync() | ✅ 正确 | ✅ 正确 | ⚠️ 契约不匹配 |
| **检索** | | | | |
| POST /api/search | searchApi.search() | ✅ 正确 | ✅ 正确 | ⚠️ 契约不匹配 |
| **培训** | | | | |
| POST /api/training/outline | trainingApi.generateOutline() | ❌ 参数错 | ❌ body 改了但端点定义不对 | ❌ 严重 |
| POST /api/training/generate | trainingApi.generatePpt() | ❌ 参数错 | ❌ body 改了但端点定义不对 | ❌ 严重 |
| GET /api/training/download/{filename} | trainingApi.download() | ✅ 正确 | — | ✅ 正确 |

---

## 五、业务逻辑检查

### ✅ 正确的逻辑

- Wiki 生成流程：文档解析 → JSON 解析 → 保存文件 → 更新索引/日志（wiki.py）
- 知识库管理：创建/删除/统计逻辑清晰（knowledge_base.py）
- 搜索功能：模糊/精确/正则搜索实现完整（search.py）

### ⚠️ 有缺陷的逻辑

| 文件:行号 | 问题 | 影响 |
|----------|------|------|
| wiki.py:144 | 文件路径来自 `raw_path / doc_info["file"]`，但 raw_path 中可能含有无效字符 | 解析可能失败 |
| document.py:206-210 | 删除 wiki 页面时 `wiki_file = wiki_path / wiki_page` 直接删除，无验证 | 如 wiki_page 含有 `../..` 可删除其他文件 |
| chat.py:94 | `keywords = set(re.findall(...))` 提取的关键词可能为空 | 导致所有页面 score=0 |
| knowledge_base.py:121-124 | `count_documents` 统计时排除 `.json` 但没有排除隐藏文件 | 可能导致统计不准确 |
| app.py:114-132 | 文档上传后自动解析但无错误通知 | 用户不知道解析是否成功 |

### 🔴 严重缺陷

| 文件:行号 | 问题 | 后果 |
|----------|------|------|
| wiki.py:135-136 | `track = json.load(f)` 如果 `文档追踪.json` 被手动删除会 crash | 解析流程中断 |
| chat.py:87 | `with open(file_path) as f: content = f.read()` 文件被并发删除会 crash | 全局异常 |
| llm.py:72-96 | LLM 请求超时、连接错误无重试机制 | 用户体验差 |

---

## 六、安全风险评估

| 风险等级 | 风险描述 | 位置 | 影响 | 修复 |
|---------|---------|------|------|------|
| 🔴 严重 | **路径遍历** - `get_wiki_page(page_name)` 无验证 | app.py:166-172 | 可读取任意 wiki 文件 | 验证 `".." not in page_name` |
| 🔴 严重 | **API Key 明文存储** - `~/.anniu/config.json` 明文保存 api_key | config.py:13-14 | 密钥泄露 | 加密存储或使用系统密钥管理 |
| 🟡 中危 | **缺失输入验证** - 文件上传无大小限制 | app.py:113-125 | DoS 攻击 | 添加 `max_upload_size=100MB` |
| 🟡 中危 | **缺失输入验证** - 知识库名称无长度限制 | models.py:59 | 资源耗尽 | 已有 `max_length=100` ✅ |
| 🔵 低危 | **LLM Prompt 注入** - 用户问题直接拼入 prompt | chat.py:169-172 | 绕过安全设置 | 对用户输入进行转义 |
| 🔵 低危 | **前端泄露 API 配置** - config.json 通过 `/api/config` 暴露 | app.py:49-52 | API Key 可能暴露 | 过滤敏感字段返回 |

---

## 七、修复优先级建议

### 🚨 立即修复（今天）

1. **ApiResponse 结构统一** - 这是阻塞问题，所有 API 调用现在都失败
   - 推荐：后端改为 `code: int = 200, success: bool = True`  
   - 前端改为检查 `!data.success || data.code !== 200`

2. **添加 CORS 中间件** - 否则前端浏览器请求会被拦截
   - 5 分钟改动，高风险

3. **修复 DocumentInfo 字段映射** - 前端显示会全部错误
   - 前后端对齐字段名和类型

### ⚡ 短期处理（本周）

4. **修复聊天页面 loading 状态** - 防止状态混乱
5. **添加路径验证** - 防止路径遍历攻击
6. **统一 training API 参数** - 当前参数位置错误
7. **修复流式 API 回调** - 无 await 导致 Promise 未捕获

### 📅 长期优化（2-4周）

8. **配置文件加密** - 保护 API Key
9. **добавить 文件上传大小限制** - 防止 DoS
10. **集成搜索索引** - 提升大文档搜索速度
11. **统一 LLM 使用 AGENTS.md** - 删除不一致

---

## 八、代码补丁示例

### 补丁 1：修复 ApiResponse 合同

**backend/models.py**
```python
class ApiResponse(BaseModel):
    """通用API响应"""
    code: int = 200  # 新增 code 字段用于兼容前端
    success: bool = True
    message: str = ""
    data: Optional[Any] = None
```

**frontend/src/lib/api.ts**
```typescript
async function request<T>(url: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${url}`, {...});
  
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.message || `HTTP ${res.status}`);
  }

  const data: ApiResponse<T> = await res.json();
  // 同时检查 success 和 code
  if (!data.success || data.code !== 200) {
    throw new Error(data.message || '请求失败');
  }
  return data.data;
}
```

### 补丁 2：添加 CORS 中间件

**backend/app.py**
```python
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(...)

# 添加CORS中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:3000",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

### 补丁 3：修复路径遍历漏洞

**backend/app.py**
```python
@app.get("/api/knowledge-bases/{kb_id}/wiki-pages/{page_name}", response_model=ApiResponse)
async def get_wiki_page(kb_id: str, page_name: str):
    """获取Wiki页面内容"""
    # 防止路径遍历，仅允许字母、数字、连字符、下划线
    if not re.match(r'^[a-zA-Z0-9_-]+$', page_name):
        raise HTTPException(status_code=400, detail="无效的页面名称")
    
    page = await wiki_service.get_wiki_page(kb_id, page_name)
    if not page:
        raise HTTPException(status_code=404, detail="Wiki页面不存在")
    return ApiResponse(data=WikiPageContent(**page))
```

### 补丁 4：修复聊天流状态管理

**frontend/src/app/components/pages/ChatPage.tsx**
```typescript
const handleSend = () => {
  if (!input.trim() || selectedKbs.length === 0 || isLoading) return;
  
  const question = input;
  setMessages(prev => [...prev, { role: 'user', content: question, time }]);
  setInput('');
  setIsLoading(true);
  
  setMessages(prev => [...prev, { role: 'assistant', content: '', time }]);
  
  chatApi.ask(
    { question, knowledge_base_ids: selectedKbs, model_id: selectedModel },
    (chunk) => {
      setMessages(prev => {
        const last = prev[prev.length - 1];
        if (last.role === 'assistant') {
          return [...prev.slice(0, -1), { ...last, content: last.content + chunk }];
        }
        return prev;
      });
    },
    (err) => {
      setMessages(prev => {
        const last = prev[prev.length - 1];
        if (last.role === 'assistant') {
          return [...prev.slice(0, -1), { ...last, content: `请求失败: ${err.message}` }];
        }
        return prev;
      });
      setIsLoading(false);  // 仅在错误时设置，成功时在完成回调设置
    }
  );
  // ❌ 删除这行 setIsLoading(false)
};
```

### 补丁 5：修复 DocumentInfo 字段映射

**frontend/src/lib/types.ts**
```typescript
export interface DocumentInfo {
  id: string;
  file: string;  // 改自 filename
  file_size_mb: number;  // 改自 size
  page_count: number;  // 改自 pages
  wiki_pages: string[];  // 改自 wiki_pages?: number
  uploaded_at: string;
  parse_status: 'pending' | 'parsing' | 'completed' | 'failed';  // 改自 status
}
```

### 补丁 6：修复培训 API 参数

**backend/app.py**
```python
@app.post("/api/training/outline", response_model=ApiResponse)
async def generate_training_outline(data: TrainingOutlineRequest):  # 改为 request body
    """生成培训大纲"""
    outline = await training_service.generate_outline(
        source_type=data.source.type,
        source_ids=data.source.ids,
        topic=data.config.topic,
        audience=data.config.audience,
        duration=data.config.duration,
        slide_count=data.config.slide_count,
        focus_areas=data.config.focus_areas,
        model_id=data.config.model_id
    )
    return ApiResponse(data=outline)
```

**frontend/src/lib/api.ts**
```typescript
generateOutline: (config: TrainingOutlineRequest) =>
  request<TrainingOutline>('/api/training/outline', {
    method: 'POST',
    body: JSON.stringify(config),  // 保持不变，改端点
  }),
```

---

## 九、遗留风险和已知问题

### 已知会持续存在的风险

- **API Key 明文存储在 `~/.anniu/config.json`** - 建议用户设置文件权限 `chmod 600`
- **LLM Prompt 注入** - 虽然可以转义，但完全防护需要 LLM 方面的安全加固
- **前端构建时缺少类型检查** - package.json 没有 `tsc --noEmit` 预检查步骤

### 建议的后续任务

1. 添加单元测试（目前 0% 覆盖）
2. 添加 E2E 测试验证前后端契约
3. 集成 TypeScript 类型检查到 CI/CD
4. 添加 API 文档生成 (OpenAPI/Swagger)
5. 性能优化：缓存、索引、分页

---

## 十、总结

**当前项目处于"编译-可否不运行"阶段**：

- ✅ 代码结构合理，功能设计完整
- ❌ **前后端契约严重不一致，导致所有 API 调用失败**
- ❌ **缺失 CORS 中间件，浏览器请求被拦截**
- ⚠️ 多个安全风险（路径遍历、明文 API Key）
- ⚠️ 流式异步处理有缺陷

**建议**：修复前 3 大问题后（估计 2 小时），项目应该能基本可用。随后逐步处理安全和稳定性问题。

---

**报告生成时间**: 2026-05-09 21:27  
**报告版本**: 1.0  
