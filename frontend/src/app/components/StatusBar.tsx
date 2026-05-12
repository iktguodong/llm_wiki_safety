// 底部状态栏：展示品牌信息与全局状态。
export default function StatusBar() {
  return (
    <div className="h-9 bg-white border-t border-slate-200 px-5 flex items-center justify-center text-xs">
      <div className="flex items-center gap-3 text-slate-500">
        <div className="flex items-center gap-2">
          <div className="w-5 h-5 rounded-full bg-indigo-600 text-white flex items-center justify-center text-[11px] font-semibold shadow-sm">
            C
          </div>
          <a
            href="https://liaoantech.com"
            target="_blank"
            rel="noreferrer"
            className="text-slate-600 font-medium hover:text-indigo-600 hover:underline"
          >
            杭州了安科技有限公司
          </a>
        </div>
        <div className="w-1 h-1 rounded-full bg-slate-300" aria-hidden="true" />
        <span className="text-slate-500">公益安全项目</span>
      </div>
    </div>
  );
}
