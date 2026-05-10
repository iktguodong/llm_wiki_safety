# 后续开发详细计划

**计划名称**: 补齐 Week 3-4 + Week 5 完整开发  
**当前状态**: 88% 完成  
**目标状态**: 100% 完成 + Beta 可部署  
**计划周期**: 5 个工作日 (5.10-5.14)  
**最终交付**: 2026-05-14 (Beta 版本)

---

## 第一部分：任务分解 & 工作量评估

### 🔴 P0 任务 (必做，2-3 天完成)

| 序号 | 任务 | 文件 | 工作量 | 优先级 | 截止日期 |
|------|------|------|--------|--------|---------|
| 1 | 前端定时同步逻辑 | App.tsx | 0.5h | 🔴 | 5.10 |
| 2 | 搜索结果分组显示 | SearchPage.tsx | 1h | 🔴 | 5.10 |
| 3 | 后端配置 API | app.py | 0.5h | 🔴 | 5.10 |
| 4 | ReaderPage 组件 | ReaderPage.tsx | 2h | 🔴 | 5.11 |
| 5 | ReaderPage 集成路由 | App.tsx | 0.5h | 🔴 | 5.11 |
| 6 | 集成测试 + Bug 修复 | tests/ | 2h | 🔴 | 5.12 |

**小计**: 6.5 小时 (约 1 个工作日 + 0.5 个工作日)

### 🟡 P1 任务 (应做，可选优化)

| 序号 | 任务 | 文件 | 工作量 | 优先级 | 截止日期 |
|------|------|------|--------|--------|---------|
| 7 | PDF 库集成 (可选) | ReaderPage.tsx | 1h | 🟡 | 5.13 |
| 8 | Word 库集成 (可选) | ReaderPage.tsx | 0.5h | 🟡 | 5.13 |
| 9 | 高亮自动恢复 | ReaderPage.tsx | 1h | 🟡 | 5.13 |
| 10 | 性能优化 | multiple | 1h | 🟡 | 5.14 |

**小计**: 3.5 小时 (可选)

---

## 第二部分：日程安排

### 📅 5月10日 (Day 1) - P0 核心功能补齐

#### ✅ Task 1: 前端定时同步 (30 分钟)

**目标**: 实现配置每 30 秒自动同步一次

**文件**: `frontend/src/app/App.tsx`

**实现代码**:
```typescript
import { useEffect } from 'react';
import { useAppState } from '@/lib/context';

export function App() {
  const appState = useAppState();
  
  // ➕ 新增定时同步逻辑
  useEffect(() => {
    // 启动时加载
    if (appState) {
      appState.syncAllConfig();
    }
    
    // 每30秒同步一次
    const syncInterval = setInterval(() => {
      if (appState) {
        appState.syncAllConfig();
      }
    }, 30000);
    
    // 清理
    return () => clearInterval(syncInterval);
  }, [appState]);
  
  // ... 其他代码
}
```

**验收标准**:
- [ ] 应用启动时调用 `syncAllConfig()`
- [ ] 之后每 30 秒自动调用一次
- [ ] 控制台无错误
- [ ] 页面切换知识库时立即生效

**测试**:
```bash
1. 启动应用，检查 Network 标签是否有 /api/config 请求
2. 等待 30 秒，再次检查是否有请求
3. 切换知识库/模型，检查状态是否立即更新
```

---

#### ✅ Task 2: 搜索结果分组显示 (1 小时)

**目标**: 前端按知识库 ID 分组展示搜索结果

**文件**: `frontend/src/app/components/pages/SearchPage.tsx`

**实现代码**:
```typescript
import { useState } from 'react';
import { searchApi } from '@/lib/api';
import type { SearchResult } from '@/lib/types';

export function SearchPage() {
  const [searchQuery, setSearchQuery] = useState('');
  const [searchResult, setSearchResult] = useState<SearchResult | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  const handleSearch = async () => {
    if (!searchQuery.trim()) return;
    
    try {
      setIsLoading(true);
      const result = await searchApi.search({
        keyword: searchQuery,
        mode: 'fuzzy',
        knowledge_base_ids: [],  // 搜索所有 KB
      });
      setSearchResult(result);
    } catch (err) {
      alert('搜索失败: ' + (err instanceof Error ? err.message : '未知错误'));
    } finally {
      setIsLoading(false);
    }
  };

  // 按知识库分组渲染
  const renderGroupedResults = () => {
    if (!searchResult?.results_grouped) {
      return <div className="text-gray-500">无结果</div>;
    }

    return (
      <div className="space-y-6">
        {Object.entries(searchResult.results_grouped).map(([kbId, matches]) => (
          <section key={kbId} className="border rounded p-4 bg-white">
            {/* 知识库标题 */}
            <h3 className="font-bold text-lg mb-3 text-blue-700">
              📚 {kbId}
              <span className="text-sm text-gray-600 ml-2">
                ({matches.length} 个匹配)
              </span>
            </h3>

            {/* 搜索结果列表 */}
            <div className="space-y-3">
              {matches.map((match, idx) => (
                <div key={`${match.file}-${match.page}-${idx}`} className="border-l-4 border-blue-300 pl-4 py-2">
                  {/* 文件和页码 */}
                  <div className="text-sm font-semibold text-gray-800">
                    📄 {match.file} <span className="text-xs text-gray-500">(页码: {match.page})</span>
                  </div>

                  {/* 相关度分数 */}
                  <div className="text-xs text-gray-500 mt-1">
                    相关度: <span className="font-semibold">{(match.score * 100).toFixed(0)}%</span>
                  </div>

                  {/* 文本片段（高亮关键词） */}
                  <div className="text-sm text-gray-700 mt-2 bg-gray-50 p-2 rounded">
                    {/* 简单高亮实现: 将关键词替换为 <mark> */}
                    {match.snippet ? (
                      <>
                        {match.snippet.split(new RegExp(`(${searchQuery})`, 'gi')).map((part, i) =>
                          part.toLowerCase() === searchQuery.toLowerCase() ? (
                            <mark key={i} className="bg-yellow-200 font-semibold">{part}</mark>
                          ) : (
                            <span key={i}>{part}</span>
                          )
                        )}
                      </>
                    ) : (
                      <span className="text-gray-500">暂无预览</span>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </section>
        ))}
      </div>
    );
  };

  return (
    <div className="h-screen flex flex-col p-6 bg-gray-100">
      {/* 搜索框 */}
      <div className="bg-white p-4 rounded mb-4 shadow">
        <div className="flex gap-2">
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
            placeholder="搜索文档内容..."
            className="flex-1 px-3 py-2 border rounded"
          />
          <button
            onClick={handleSearch}
            disabled={isLoading}
            className="px-4 py-2 bg-blue-500 text-white rounded hover:bg-blue-600 disabled:opacity-50"
          >
            {isLoading ? '搜索中...' : '🔍 搜索'}
          </button>
        </div>
        {searchResult && (
          <div className="text-sm text-gray-600 mt-2">
            找到 {searchResult.total_matches} 个匹配
          </div>
        )}
      </div>

      {/* 搜索结果 */}
      <div className="flex-1 overflow-auto bg-white p-4 rounded">
        {isLoading ? (
          <div className="flex items-center justify-center h-full">
            <p className="text-gray-500">搜索中...</p>
          </div>
        ) : searchResult ? (
          renderGroupedResults()
        ) : (
          <div className="text-gray-400 text-center py-20">
            输入关键词搜索文档
          </div>
        )}
      </div>
    </div>
  );
}
```

**验收标准**:
- [ ] 搜索结果按知识库 ID 分组展示
- [ ] 每个 KB 组显示匹配数量
- [ ] 关键词高亮显示（黄色背景）
- [ ] 显示相关度分数
- [ ] 显示文件名和页码

**测试**:
```bash
1. 输入关键词搜索
2. 验证结果按 KB 分组
3. 验证关键词亮显
4. 切换搜索词，结果更新
```

---

#### ✅ Task 3: 后端配置 API (30 分钟)

**目标**: 确保配置切换 API 完整

**文件**: `backend/app.py`

**需求检查清单**:

1. ❓ 是否存在 `GET /api/config/current-kb`？
   - 如不存在，添加：
   ```python
   @router.get("/api/config/current-kb", response_model=ApiResponse)
   async def get_current_kb():
       """获取当前知识库"""
       return ApiResponse(data={"id": config.get("current_kb_id")})
   ```

2. ❓ 是否存在 `POST /api/config/current-kb`？
   - 如不存在，添加：
   ```python
   @router.post("/api/config/current-kb", response_model=ApiResponse)
   async def set_current_kb(request: dict):
       """设置当前知识库"""
       kb_id = request.get("id")
       config["current_kb_id"] = kb_id
       save_config(config)
       return ApiResponse(message="知识库已切换")
   ```

3. ❓ 是否存在 `GET /api/config/current-model`？
   - 如不存在，添加：
   ```python
   @router.get("/api/config/current-model", response_model=ApiResponse)
   async def get_current_model():
       """获取当前模型"""
       return ApiResponse(data={"id": config.get("current_model_id", "deepseek-chat")})
   ```

4. ❓ 是否存在 `POST /api/config/current-model`？
   - 如不存在，添加：
   ```python
   @router.post("/api/config/current-model", response_model=ApiResponse)
   async def set_current_model(request: dict):
       """设置当前模型"""
       model_id = request.get("id")
       config["current_model_id"] = model_id
       save_config(config)
       return ApiResponse(message="模型已切换")
   ```

**验收标准**:
- [ ] 4 个 API 都存在且可调用
- [ ] GET 返回当前配置
- [ ] POST 能更新配置并持久化
- [ ] 返回结构符合 ApiResponse

**测试**:
```bash
curl -X GET http://localhost:8000/api/config/current-kb
curl -X POST http://localhost:8000/api/config/current-kb -H "Content-Type: application/json" -d '{"id":"kb-123"}'
```

---

### 📅 5月11日 (Day 2) - ReaderPage 组件实现

#### ✅ Task 4: 创建 ReaderPage 组件 (2 小时)

**目标**: 实现原文阅读器基础功能（页码切换、高亮、搜索框架）

**文件**: `frontend/src/app/components/pages/ReaderPage.tsx` (新建)

**实现代码**:
```typescript
import React, { useState, useEffect } from 'react';
import { useParams } from 'react-router-dom';
import { Button } from '@/app/components/ui/button';
import { documentsApi } from '@/lib/api';

interface Document {
  id: string;
  fileName: string;
  fileType: 'pdf' | 'docx' | 'md';
  totalPages: number;
  content: string;
}

export function ReaderPage() {
  const { docId } = useParams<{ docId: string }>();
  const [document, setDocument] = useState<Document | null>(null);
  const [currentPage, setCurrentPage] = useState(1);
  const [isLoading, setIsLoading] = useState(true);
  const [selectedText, setSelectedText] = useState('');
  const [highlights, setHighlights] = useState<Array<{ start: number; end: number }>>([]);
  const [searchKeyword, setSearchKeyword] = useState('');

  // 加载文档
  useEffect(() => {
    if (!docId) return;
    
    loadDocument();
  }, [docId]);

  const loadDocument = async () => {
    try {
      setIsLoading(true);
      // TODO: 从后端获取文档内容
      // const content = await documentsApi.getContent(docId);
      
      // 临时示例数据（实际应从后端获取）
      setDocument({
        id: docId!,
        fileName: 'sample.pdf',
        fileType: 'pdf',
        totalPages: 10,
        content: '文档内容示例...',
      });
    } catch (err) {
      console.error('加载文档失败:', err);
    } finally {
      setIsLoading(false);
    }
  };

  // 处理文本选中（高亮）
  const handleTextSelection = () => {
    const selected = window.getSelection()?.toString() || '';
    setSelectedText(selected);
  };

  // 添加高亮
  const handleHighlight = async () => {
    if (!selectedText || !docId) return;

    try {
      // 保存高亮到后端
      // await documentsApi.saveHighlight(docId, { text: selectedText });
      
      // 本地更新
      setHighlights([
        ...highlights,
        { start: 0, end: selectedText.length }
      ]);
      setSelectedText('');
      alert('已添加高亮');
    } catch (err) {
      console.error('添加高亮失败:', err);
    }
  };

  // 删除高亮
  const handleClearHighlights = () => {
    setHighlights([]);
    alert('已清空所有高亮');
  };

  // 页码切换
  const handlePrevPage = () => {
    if (currentPage > 1) setCurrentPage(currentPage - 1);
  };

  const handleNextPage = () => {
    if (document && currentPage < document.totalPages) {
      setCurrentPage(currentPage + 1);
    }
  };

  // 搜索功能（框架）
  const handleSearch = () => {
    if (!document || !searchKeyword) return;
    
    // TODO: 实现搜索逻辑
    // 在当前文档内搜索关键词，高亮匹配项
    alert(`搜索"${searchKeyword}"的功能将在后续版本实现`);
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-screen">
        <p className="text-gray-500">加载文档中...</p>
      </div>
    );
  }

  if (!document) {
    return (
      <div className="flex items-center justify-center h-screen">
        <p className="text-red-500">文档加载失败</p>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-screen bg-gray-100">
      {/* 顶部工具栏 */}
      <div className="bg-white shadow p-4 flex items-center justify-between">
        <h2 className="text-lg font-bold">{document.fileName}</h2>

        <div className="flex gap-3 items-center">
          {/* 页码导航 */}
          <Button
            variant="outline"
            onClick={handlePrevPage}
            disabled={currentPage <= 1}
          >
            ← 上一页
          </Button>

          <span className="text-sm font-medium px-3 py-2">
            {currentPage} / {document.totalPages}
          </span>

          <Button
            variant="outline"
            onClick={handleNextPage}
            disabled={currentPage >= document.totalPages}
          >
            下一页 →
          </Button>

          {/* 高亮管理 */}
          <Button
            variant="outline"
            onClick={handleHighlight}
            disabled={!selectedText}
            className={selectedText ? 'bg-yellow-100' : ''}
          >
            🖍️ 高亮 ({highlights.length})
          </Button>

          <Button
            variant="ghost"
            onClick={handleClearHighlights}
            disabled={highlights.length === 0}
          >
            ✕ 清空
          </Button>
        </div>
      </div>

      {/* 搜索栏 */}
      <div className="bg-white border-b p-3 flex gap-2">
        <input
          type="text"
          value={searchKeyword}
          onChange={(e) => setSearchKeyword(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
          placeholder="在文档中搜索..."
          className="flex-1 px-3 py-2 border rounded"
        />
        <Button onClick={handleSearch}>🔍 搜索</Button>
      </div>

      {/* 文档内容区域 */}
      <div
        className="flex-1 overflow-auto p-6 bg-white"
        onMouseUp={handleTextSelection}
      >
        <div className="max-w-4xl mx-auto bg-white p-6 shadow">
          {/* 显示选中的文本 */}
          {selectedText && (
            <div className="bg-yellow-50 border-l-4 border-yellow-400 p-3 mb-4">
              <strong>已选中:</strong> "{selectedText.substring(0, 50)}..."
            </div>
          )}

          {/* 文档内容 */}
          <div className="prose max-w-none">
            {document.fileType === 'pdf' ? (
              <p className="text-gray-500">[PDF 阅读器 - 等待 PDF.js 库集成]</p>
            ) : document.fileType === 'docx' ? (
              <p className="text-gray-500">[Word 阅读器 - 等待 docx 库集成]</p>
            ) : document.fileType === 'md' ? (
              <div dangerouslySetInnerHTML={{ __html: document.content }} />
            ) : null}
          </div>
        </div>
      </div>

      {/* 底部状态栏 */}
      <div className="bg-white border-t p-3 text-sm text-gray-600">
        <p>
          已添加 <strong>{highlights.length}</strong> 个高亮 | 当前页面: <strong>{currentPage}</strong>
        </p>
      </div>
    </div>
  );
}
```

**验收标准**:
- [ ] 页面可显示文档名称
- [ ] 页码导航正常工作
- [ ] 能选中文本并显示
- [ ] 高亮按钮可用
- [ ] 搜索框架完整
- [ ] 无运行时错误

**测试**:
```bash
1. 访问 /reader/doc-123
2. 检查页码是否正常显示
3. 选中文本，检查"已选中"提示
4. 点击高亮按钮
5. 输入搜索词
```

---

#### ✅ Task 5: 集成 ReaderPage 路由 (30 分钟)

**目标**: 将 ReaderPage 集成到应用路由

**文件**: `frontend/src/app/App.tsx`

**修改**:
```typescript
// 导入 ReaderPage
import { ReaderPage } from './components/pages/ReaderPage';

// 在 Routes 中添加路由
<Routes>
  {/* 其他路由 */}
  <Route path="/reader/:docId" element={<ReaderPage />} />
</Routes>
```

**验收标准**:
- [ ] 导航到 `/reader/doc-123` 能打开阅读器
- [ ] 其他页面路由不受影响

---

### 📅 5月12日 (Day 3) - 集成测试 & Bug 修复

#### ✅ Task 6: 完整集成测试 (2 小时)

**测试清单**:

```bash
# 1. 后端 API 测试
[ ] 测试所有新增 API (current-kb, current-model)
[ ] 测试搜索 API 返回 results_grouped
[ ] 测试文档高亮存储 API

# 2. 前端功能测试
[ ] 应用启动时调用 syncAllConfig()
[ ] 30 秒后自动同步一次
[ ] 知识库切换后立即生效
[ ] 模型切换后立即生效
[ ] 搜索结果正确分组
[ ] 搜索结果显示高亮
[ ] ReaderPage 能打开
[ ] 页码导航工作正常

# 3. 端到端流程测试
[ ] 新建知识库 → 上传文件 → 解析 → 搜索 → 查看原文
[ ] 知识问答流程
[ ] 配置切换后所有功能正常

# 4. 浏览器兼容性测试
[ ] Chrome
[ ] Firefox
[ ] Safari (可选)

# 5. 性能测试
[ ] 搜索响应时间 < 500ms
[ ] 页面切换流畅
[ ] 内存占用合理
```

**运行测试**:

```bash
# 后端单元测试
cd backend
python -m pytest tests/test_full_workflow.py -v

# 前端手动测试（逐项检查上述清单）
cd frontend
npm run dev
# 打开浏览器访问 http://localhost:5173
```

**Bug 修复流程**:
1. 记录发现的问题
2. 分类：前端/后端/集成
3. 优先修复阻塞性 bug
4. 重新测试
5. 记录修复清单

---

### 📅 5月13日 (Day 4) - 可选优化

#### 🟡 Task 7-10: P1 任务（可选）

**可选项**:
- [ ] 集成 `pdfjs-dist` 库支持 PDF 查看
- [ ] 集成 `docx` 库支持 Word 查看
- [ ] 实现高亮自动恢复（刷新后恢复之前的高亮）
- [ ] 性能优化（缓存、防抖、节流）

**工作量**: 每项 0.5-1 小时

---

### 📅 5月14日 (Day 5) - 验收 & 精细调优

#### ✅ Task 11: 最终验收 & 部署准备

**验收清单**:

```bash
# 功能完整性
[ ] Week 1-2 所有功能正常
[ ] Week 3 搜索/配置功能正常
[ ] Week 4 阅读器框架可用
[ ] 无阻塞性 bug

# 代码质量
[ ] 无语法错误
[ ] 无运行时错误
[ ] 代码注释完整
[ ] 遵循代码规范

# 文档
[ ] API 文档更新
[ ] 功能说明更新
[ ] 部署指南准备

# 性能
[ ] 响应时间在目标范围内
[ ] 内存占用正常
[ ] 无内存泄漏

# 安全
[ ] 路径遍历防护（✓ 已做）
[ ] API Key 不暴露
[ ] 输入验证完整
```

**部署准备**:

```bash
# 后端打包
docker build -t anniu-backend:beta -f backend/Dockerfile .

# 前端构建
npm run build

# 生成部署清单
mkdir -p deployment/
cp -r dist/ deployment/frontend/
cp -r backend/ deployment/backend/
cp deploy-guide.md deployment/
```

---

## 第三部分：验收标准 & 交付物

### 🎯 功能验收标准

| 功能模块 | 验收标准 | 优先级 |
|---------|---------|--------|
| 配置同步 | 30s 自动同步，立即更新生效 | P0 |
| 搜索分组 | 按 KB 分组，关键词高亮 | P0 |
| 阅读器 | 页码导航，高亮，搜索框架 | P0 |
| 后端 API | 4 个配置 API 完整可用 | P0 |
| 集成测试 | 0 个阻塞性 bug | P0 |
| PDF 支持 | 可选，可后期补充 | P1 |

### 📦 交付物清单

| # | 交付物 | 类型 | 说明 |
|----|--------|------|------|
| 1 | 完整源代码 | 代码 | Week 1-4 所有代码 |
| 2 | 部署指南 | 文档 | 本地/线上部署说明 |
| 3 | API 文档 | 文档 | 所有 API 接口说明 |
| 4 | 功能说明 | 文档 | 用户功能使用文档 |
| 5 | 测试报告 | 测试 | 测试覆盖范围和结果 |
| 6 | 性能报告 | 测试 | 性能基准数据 |
| 7 | Docker 镜像 | 部署 | 后端容器镜像 |
| 8 | 前端构建物 | 部署 | 可直接部署的前端文件 |

---

## 第四部分：风险管理

### 🔴 高风险项

| 风险 | 影响 | 缓解方案 |
|------|------|---------|
| PDF.js 集成延期 | 可选，不影响 | 5.13 后补充 |
| 性能问题出现 | 需优化 | 使用缓存、防抖、分页 |
| 并发同步冲突 | 配置错乱 | 添加请求去重、锁机制 |

### 🟡 中风险项

| 风险 | 影响 | 缓解方案 |
|------|------|---------|
| 高亮保存失败 | 用户体验下降 | 本地备份，异步重试 |
| 大文件加载慢 | 可用性降低 | 分块加载、虚拟滚动 |

---

## 第五部分：日报模板

### 每日进度报告

```
【日期】5.10
【任务完成】
- [x] 前端定时同步 (100%)
- [x] 搜索分组显示 (100%)
- [x] 后端配置 API (100%)

【遇到的问题】
- API 返回格式不一致，已修复

【明日计划】
- 实现 ReaderPage 组件
- 集成路由

【代码提交】
- commit abc123 - Add sync timer and grouped search
```

---

## 总结

```
┌─────────────────────────────────┐
│   5 天开发冲刺计划总结          │
├─────────────────────────────────┤
│ Day 1: P0 核心功能 (3 task)     │
│ Day 2: ReaderPage (2 task)      │
│ Day 3: 集成测试 (1 task)        │
│ Day 4: 可选优化 (4 task)        │
│ Day 5: 验收部署 (1 task)        │
│                                 │
│ 总工作量: 13.5 小时 (P0) +      │
│          3.5 小时 (P1)          │
│                                 │
│ 预期结果: Beta 版本可部署        │
│ 交付日期: 2026-05-14            │
└─────────────────────────────────┘
```

---

**注意**: 此计划为详细执行指南，涵盖代码、测试、验收全流程。如开发进度超前，可提前进行 P1 优化项；如有延迟，可在 Day 4-5 调整。每天结束时更新日报，便于追踪进度。

