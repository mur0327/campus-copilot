export function HeaderBar() {
  return (
    <header className="flex h-[5.75rem] shrink-0 items-center justify-between border-b border-slate-200 bg-white px-10">
      <div>
        <p className="text-base font-semibold text-sky-800">호남대학교</p>
        <h1 className="text-[2rem] font-bold leading-tight tracking-tight">Campus Copilot</h1>
      </div>
      <div className="text-right">
        <p className="text-base font-semibold text-slate-700">학사 안내 키오스크</p>
        <p className="mt-1 text-sm text-slate-500">자주 찾는 안내와 질문 입력을 함께 제공합니다</p>
      </div>
    </header>
  );
}
