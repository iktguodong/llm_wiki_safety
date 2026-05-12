// 底部状态栏：展示品牌信息与全局状态。
export default function StatusBar() {
  return (
    <div className="h-9 bg-white border-t border-slate-200 px-5 flex items-center justify-center text-xs">
      <div className="flex items-center gap-3 text-slate-500">
        <div className="flex items-center gap-2">
          <span className="text-slate-400 text-[14px] leading-none font-medium">©</span>
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
