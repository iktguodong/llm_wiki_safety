import { ExternalLink, Github, RefreshCw, HeartHandshake, BookOpen } from 'lucide-react';

export default function AboutPage() {
  const handleCheckUpdate = () => {
    window.open('https://github.com/iktguodong/llm_wiki_safety/releases', '_blank');
  };

  return (
    <div className="h-full flex flex-col bg-slate-50">
      {/* Header */}
      <div className="flex-shrink-0 bg-white border-b border-slate-200 px-8 py-5">
        <h1 className="text-slate-900">关于</h1>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-auto px-8 py-6 space-y-5">
        {/* Brand card */}
        <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
          <div className="px-8 py-8">
            <h2 className="text-2xl text-slate-900" style={{ fontWeight: 600 }}>安牛（AnNiu）</h2>
            <p className="text-base text-slate-500 mt-1">个人安全知识库助手</p>
          </div>
        </div>

        {/* Description card */}
        <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
          <div className="px-8 py-6">
            <ol className="text-sm text-slate-600 leading-relaxed space-y-4 list-decimal pl-5">
              <li className="pl-1">
                “安牛”个人安全知识库助手，由<strong>杭州了安科技有限公司</strong>开发，是一个面向安全生产知识工作者的公益安全项目。
              </li>
              <li className="pl-1">
                “安牛”基于 LLM Wiki 构建，支持将用户上传的安全生产、应急预案、安全制度、培训材料等文档转化为结构化 Wiki 页面，并进一步用于知识库问答、原文检索、Wiki 质量检查和培训材料生成。
              </li>
              <li className="pl-1">
                “安牛”的目标为安全生产知识工作者提供一个专业、可追溯、可检索、可复用的 AI 辅助工具，帮助用户更高效地整理、检索、理解和复用安全知识。
              </li>
              <li className="pl-1">
                欢迎熟悉安全生产行业的 AI 爱好者、安全管理人员、开发者提供建议和意见，也欢迎参与开源项目建设，提交 Issue、贡献编辑内容或提交 Pull Request。希望大家共同完善这个公益安全项目，为安全生产工作尽一份力。
              </li>
            </ol>
          </div>
        </div>

        {/* Info cards */}
        <div className="grid grid-cols-1 gap-4">
          {/* Developer */}
          <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
            <div className="px-6 py-4 flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className="w-8 h-8 rounded-lg bg-indigo-50 flex items-center justify-center flex-shrink-0">
                  <HeartHandshake className="w-4 h-4 text-indigo-600" />
                </div>
                <div>
                  <div className="text-sm text-slate-500">开发单位</div>
                  <a
                    href="https://liaoantech.com"
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-sm text-indigo-600 hover:text-indigo-700 hover:underline inline-flex items-center gap-1"
                  >
                    杭州了安科技有限公司
                    <ExternalLink className="w-3 h-3" />
                  </a>
                </div>
              </div>
            </div>
          </div>

          {/* Open source */}
          <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
            <div className="px-6 py-4 flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className="w-8 h-8 rounded-lg bg-indigo-50 flex items-center justify-center flex-shrink-0">
                  <Github className="w-4 h-4 text-indigo-600" />
                </div>
                <div>
                  <div className="text-sm text-slate-500">GitHub 开源地址</div>
                  <a
                    href="https://github.com/iktguodong/llm_wiki_safety"
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-sm text-indigo-600 hover:text-indigo-700 hover:underline inline-flex items-center gap-1"
                  >
                    https://github.com/iktguodong/llm_wiki_safety
                    <ExternalLink className="w-3 h-3" />
                  </a>
                </div>
              </div>
            </div>
          </div>

          {/* Version & Update */}
          <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
            <div className="px-6 py-4 flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className="w-8 h-8 rounded-lg bg-indigo-50 flex items-center justify-center flex-shrink-0">
                  <BookOpen className="w-4 h-4 text-indigo-600" />
                </div>
                <div>
                  <div className="text-sm text-slate-500">当前版本</div>
                  <div className="text-sm text-slate-900" style={{ fontWeight: 500 }}>v1.0.0</div>
                </div>
              </div>
              <button
                onClick={handleCheckUpdate}
                className="flex items-center gap-1.5 px-4 py-2 border border-slate-200 text-slate-700 rounded-lg text-sm hover:bg-slate-50 transition-colors"
              >
                <RefreshCw className="w-3.5 h-3.5" />
                检查更新
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
