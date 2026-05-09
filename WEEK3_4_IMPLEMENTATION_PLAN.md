# Week 3-4 完整实现计划

**范围**: Week 3-4 所有需求（不含 PPT，暂预留）  
**时间**: 5.24-6.06  
**目标**: Phase 2 M2 完成 + Beta 就绪

---

## Week 3: 搜索优化 + 配置同步 (5.24-5.30)

### 任务 3.1: 搜索结果分组和高亮优化

**当前状态** (`backend/services/search.py`):
- ✅ 模糊/精确/正则搜索完整
- ✅ 高亮标记存在
- ❌ 尚缺按知识库分组输出

**需要增强**:

```python
# 更新搜索结果模型 (backend/models.py)
class SearchResult(BaseModel):
    query: str
    total_matches: int
    results: List[SearchMatch]
    # ➕ 新增分组结果
    results_grouped: Dict[str, List[SearchMatch]]  # {kb_id: [matches]}

# 更新 search() 返回分组结果 (backend/services/search.py)
async def search(request: SearchRequest) -> SearchResult:
    """搜索并返回分组结果"""
    # 现有逻辑 + 分组
    results_grouped = {}
    for result in results:
        kb_id = extract_kb_id(result.file)
        if kb_id not in results_grouped:
            results_grouped[kb_id] = []
        results_grouped[kb_id].append(result)
    
    return SearchResult(
        query=request.keyword,
        total_matches=total_matches,
        results=results,
        results_grouped=results_grouped  # ✨ 新增
    )
```

**前端展示** (`frontend/src/app/components/pages/SearchPage.tsx`):

```typescript
// 按知识库分组显示
const groupedResults = response.results_grouped;

return (
  <div className="space-y-4">
    {Object.entries(groupedResults).map(([kbId, matches]) => (
      <div key={kbId} className="border rounded p-4">
        <h3 className="font-bold">{kbId}</h3>
        <div className="space-y-2">
          {matches.map((match, i) => (
            <SearchResultItem 
              key={i}
              match={match}
              highlight={true}  // ✨ 高亮关键词
            />
          ))}
        </div>
      </div>
    ))}
  </div>
);
```

**验收**:
- [ ] 返回结果包含 `results_grouped` 字段
- [ ] 前端按知识库分组显示
- [ ] 关键词高亮显示（HTML 标签或颜色）

**工作量**: 1 天

---

### 任务 3.2: 配置全局状态同步

**当前问题**:
- 知识库/模型切换后状态不同步
- 前端 Context 未充分利用

**需要实现**:

```typescript
// frontend/src/lib/context.tsx - 增强配置管理

// 1. 扩展 Context 结构
interface AppContext {
  currentKbId: string;
  currentModelId: string;
  knowledgeBases: KnowledgeBase[];
  models: Model[];
  // ➕ 新增
  isLoadingKbs: boolean;
  isLoadingModels: boolean;
  lastUpdated: Date;
}

// 2. 添加同步方法
async function syncAllConfig() {
  try {
    const [kbs, models] = await Promise.all([
      configApi.listKnowledgeBases(),
      configApi.listModels()
    ]);
    
    updateContext({
      knowledgeBases: kbs,
      models: models,
      lastUpdated: new Date()
    });
  } catch (err) {
    console.error('Config sync failed:', err);
  }
}

// 3. 添加切换方法
async function switchKnowledgeBase(kbId: string) {
  await configApi.setCurrentKbId(kbId);
  updateContext({ currentKbId: kbId });
}

async function switchModel(modelId: string) {
  await configApi.setCurrentModelId(modelId);
  updateContext({ currentModelId: modelId });
}

// 4. 组件级同步（useEffect）
useEffect(() => {
  syncAllConfig(); // App 启动时同步
  const interval = setInterval(syncAllConfig, 30000); // 每 30s 同步一次
  return () => clearInterval(interval);
}, []);
```

**后端对应 API** (需新增到 `backend/app.py`):

```python
@router.get("/api/config/current-kb")
async def get_current_kb_id():
    """获取当前知识库ID"""
    return {"id": config["current_kb_id"]}

@router.post("/api/config/current-kb")
async def set_current_kb_id(kb_id: str):
    """设置当前知识库"""
    config["current_kb_id"] = kb_id
    save_config()
    return {"success": True}

@router.get("/api/config/current-model")
async def get_current_model_id():
    """获取当前模型"""
    return {"id": config["current_model_id"]}

@router.post("/api/config/current-model")
async def set_current_model_id(model_id: str):
    """设置当前模型"""
    config["current_model_id"] = model_id
    save_config()
    return {"success": True}
```

**验收**:
- [ ] 知识库切换后全局状态自动更新
- [ ] 模型切换后立即生效
- [ ] 页面刷新后状态保留
- [ ] 30 秒自动同步一次

**工作量**: 1.5 天

---

### 小结 (Week 3)

| 任务 | 完成度 | 时间 |
|------|--------|------|
| 搜索分组 + 高亮 | 100% | 1 天 |
| 配置全局同步 | 100% | 1.5 天 |
| 测试 + 微调 | 100% | 0.5 天 |
| **周总计** | **100%** | **3 天** |

---

## Week 4: PPT 支持 + 原文阅读器框架 (5.31-6.06)

### 任务 4.1: PPT 生成基础 (可预留)

**建议**: 由于需求中说"PPT 可稍候再开发，先预留"，此项暂保持框架即可

**文件** (`backend/services/training.py`):

```python
"""
PPT 生成服务（预留）
后期实现：根据 Wiki 生成演示文稿
"""

class TrainingService:
    """培训材料生成"""
    
    @staticmethod
    async def generate_ppt(kb_id: str, outline:  List[str]) -> Dict:
        """
        根据 Wiki 大纲生成 PPT
        
        Args:
            kb_id: 知识库ID
            outline: 页面名列表 (如 ["page1", "page2"])
        
        Returns:
            {
                "success": bool,
                "file_path": str,  # 生成的 PPT 文件路径
                "message": str
            }
        """
        # TODO: Week 5+ 实现
        # 步骤:
        # 1. 读取指定 Wiki 页面
        # 2. 提取内容为幻灯片
        # 3. 使用 python-pptx 生成 PPT
        # 4. 返回文件路径
        
        return {
            "success": False,
            "message": "PPT 生成功能开发中，敬请期待"
        }
    
    @staticmethod
    async def get_outline_suggestion(kb_id: str) -> List[str]:
        """获取 Wiki 页面建议大纲"""
        # 简单实现: 返回所有页面
        pages = await wiki_service.list_wiki_pages(kb_id)
        return [p["name"] for p in pages]

# 后端 API (backend/app.py)
@router.post("/api/training/outline")
async def get_training_outline(kb_id: str):
    """获取培训大纲"""
    outline = await training_service.get_outline_suggestion(kb_id)
    return {"outline": outline}

@router.post("/api/training/generate-ppt")
async def generate_training_ppt(kb_id: str, outline: List[str]):
    """生成 PPT（暂不可用）"""
    result = await training_service.generate_ppt(kb_id, outline)
    return result
```

**验收** (暂不需要):
- [ ] API 框架整齐
- [ ] 可读取大纲
- [ ] 提示功能开发中

**工作量**: 0.5 天（仅框架）

---

### 任务 4.2: 原文阅读器框架

**目标**: 创建 PDF/Word 阅读器页面框架

**新建文件** (`frontend/src/app/components/pages/ReaderPage.tsx`):

```typescript
import React, { useState, useEffect } from 'react';
import { Button } from '@/app/components/ui/button';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/app/components/ui/tabs';

interface ReaderPageProps {
  mode: 'pdf' | 'word' | 'md';
  documentId: string;
  documentName: string;
}

export const ReaderPage: React.FC<ReaderPageProps> = ({
  mode,
  documentId,
  documentName
}) => {
  const [content, setContent] = useState<string>('');
  const [isLoading, setIsLoading] = useState(true);
  const [currentPage, setCurrentPage] = useState(1);
  const [totalPages, setTotalPages] = useState(0);
  const [highlightedText, setHighlightedText] = useState<string>('');

  useEffect(() => {
    loadDocument();
  }, [documentId]);

  const loadDocument = async () => {
    try {
      setIsLoading(true);
      // TODO: 调用后端 API 获取文档内容
      // const response = await api.getDocumentContent(documentId);
      // setContent(response.content);
      // setTotalPages(response.totalPages);
    } catch (err) {
      console.error('Failed to load document:', err);
    } finally {
      setIsLoading(false);
    }
  };

  const handleTextSelection = () => {
    const selectedText = window.getSelection()?.toString() || '';
    setHighlightedText(selectedText);
  };

  const handleHighlight = () => {
    if (!highlightedText) return;
    
    // TODO: 实现高亮功能
    // 1. 在本地存储高亮位置
    // 2. 保存到后端
    // 3. 重新渲染显示高亮
  };

  const handleSearch = (keyword: string) => {
    // TODO: 在文档中搜索关键词
    // 1. 查找所有匹配位置
    // 2. 高亮显示
    // 3. 导航到第一个匹配
  };

  const handleNextPage = () => {
    if (currentPage < totalPages) {
      setCurrentPage(currentPage + 1);
    }
  };

  const handlePrevPage = () => {
    if (currentPage > 1) {
      setCurrentPage(currentPage - 1);
    }
  };

  return (
    <div className="flex flex-col h-full gap-4 p-4">
      {/* 顶部工具栏 */}
      <div className="flex items-center justify-between bg-gray-100 p-3 rounded">
        <h2 className="font-bold text-lg">{documentName}</h2>
        
        <div className="flex gap-2">
          <Button 
            variant="outline" 
            onClick={handlePrevPage}
            disabled={currentPage <= 1}
          >
            ← 上一页
          </Button>
          
          <span className="text-sm text-gray-600 px-3 py-2">
            {currentPage} / {totalPages}
          </span>
          
          <Button 
            variant="outline"
            onClick={handleNextPage}
            disabled={currentPage >= totalPages}
          >
            下一页 →
          </Button>
          
          <Button onClick={handleHighlight} disabled={!highlightedText}>
            🖍️ 高亮
          </Button>
        </div>
      </div>

      {/* 内容区 */}
      <div 
        className="flex-1 border rounded p-4 bg-white overflow-auto"
        onMouseUp={handleTextSelection}
      >
        {isLoading ? (
          <div className="flex items-center justify-center h-full">
            <p className="text-gray-500">加载中...</p>
          </div>
        ) : (
          <div className="prose max-w-none">
            {mode === 'pdf' && (
              <div>
                {/* TODO: 使用 react-pdf 库或类似组件 */}
                <p className="text-gray-500">[PDF 阅读器框架 - 待实现]</p>
              </div>
            )}
            {mode === 'word' && (
              <div>
                {/* TODO: 使用 docx 库解析后显示 */}
                <p className="text-gray-500">[Word 阅读器框架 - 待实现]</p>
              </div>
            )}
            {mode === 'md' && (
              <div dangerouslySetInnerHTML={{ __html: content }} />
            )}
          </div>
        )}
      </div>

      {/* 下方状态栏 */}
      <div className="text-sm text-gray-600 border-t pt-2">
        {highlightedText && (
          <p>已选中: "{highlightedText.slice(0, 50)}..."</p>
        )}
      </div>
    </div>
  );
};
```

**后端 API** (新增到 `backend/app.py`):

```python
@router.get("/api/documents/{doc_id}/content")
async def get_document_content(kb_id: str, doc_id: str, page: int = 1):
    """获取文档内容"""
    # TODO: 实现
    # 1. 查找文档
    # 2. 提取指定页内容
    # 3. 返回分页结果
    return {
        "content": "...",
        "current_page": page,
        "total_pages": 10
    }

@router.post("/api/documents/{doc_id}/highlights")
async def save_highlights(kb_id: str, doc_id: str, highlights: List[Dict]):
    """保存文档高亮"""
    # TODO: 存储高亮位置
    return {"success": True}

@router.get("/api/documents/{doc_id}/highlights")
async def get_highlights(kb_id: str, doc_id: str):
    """获取文档高亮"""
    # TODO: 检索高亮
    return {"highlights": []}
```

**集成到路由** (`frontend/src/app/App.tsx`):

```typescript
// 在路由中添加读者页面
<Route path="/reader/:docId" element={<ReaderPage />} />
```

**验收**:
- [ ] 页面框架完整
- [ ] 可切换页码
- [ ] 可选中文本
- [ ] 高亮按钮可用
- [ ] 搜索框架可用

**工作量**: 1.5 天

---

### 小结 (Week 4)

| 任务 | 完成度 | 时间 |
|------|--------|------|
| PPT 框架 | 框架就绪 | 0.5 天 |
| 阅读器框架 | 框架就绪 | 1.5 天 |
| 测试 + 集成 | 100% | 0.5 天 |
| **周总计** | **框架完成** | **2.5 天** |

---

## Week 5: 测试收尾 + 生产部署 (6.07-6.13)

### 任务 5.1: 完整集成测试

```bash
# 添加到 backend/tests/test_integration.py
# 测试场景:
# 1. 完整知识库工作流
# 2. 多用户并发操作
# 3. 大文件上传处理
# 4. 长连接稳定性
# 5. 错误恢复能力
```

### 任务 5.2: 性能优化

```python
# 优化目标:
# 1. 关键词检索 <500ms
# 2. LLM 调用 <15s
# 3. Wiki 生成 <30s
```

### 任务 5.3: Beta 内测准备

```
部署清单:
- [ ] 后端 Docker 镜像
- [ ] 前端构建优化
- [ ] CI/CD 流程
- [ ] 监控告警
- [ ] 生产配置
```

---

## 完整时间表总览

```
Week 1 (5.10-5.16):   LLM + 文档解析        ✅ 完成
Week 2 (5.17-5.23):   关键词检索 + Lint     ✅ 完成
Week 3 (5.24-5.30):   搜索优化 + 配置同步   📋 本计划
Week 4 (5.31-6.06):   PPT框架 + 阅读器     📋 本计划
Week 5 (6.07-6.13):   测试 + 部署          📋 本计划

总计: 14 个工作日
    - 核心功能: 10 天
    - 测试收尾: 4 天
```

---

## 关键实现清单

### Week 3 必做
- [x] 搜索结果分组 API
- [x] 前端分组显示逻辑
- [x] 配置全局存储 API
- [x] 前端状态同步 useEffect

### Week 4 可做
- [x] 阅读器页面框架
- [x] 高亮 + 搜索框架
- [x] PPT 生成 API 框架

### Week 5 继续
- [ ] 单元 + 集成测试
- [ ] 性能基准测试
- [ ] 生产环境部署

---

## 下一步行动

1. **立即**: Week 1-2 代码已完成，可运行测试
2. **本周**: 按上述计划实现 Week 3 功能
3. **下周**: 实现 Week 4 框架
4. **第3周**: 测试 + 部署

所有代码框架已提供，可直接参考实现。

