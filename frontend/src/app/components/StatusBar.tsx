// 底部状态栏：仅保留全局状态指示（已就绪）。
// 知识库与模型切换统一由各页面顶部的选择区负责，避免上下重复。
export default function StatusBar() {
  return (
    <div className="h-9 bg-white border-t border-slate-200 px-5 flex items-center justify-center text-xs">
      <div className="flex items-center gap-1.5">
        <div className="w-1.5 h-1.5 rounded-full bg-green-500"></div>
        <span className="text-slate-400">已就绪</span>
      </div>
    </div>
  );
}
