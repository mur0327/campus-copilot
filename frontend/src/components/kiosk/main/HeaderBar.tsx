export function HeaderBar() {
  return (
    <header className="flex h-24 shrink-0 items-center justify-between border-b border-slate-200 bg-white px-10">
      <div>
        <p className="text-lg font-semibold text-sky-800">호남대학교</p>
        <h1 className="text-3xl font-bold tracking-tight">Campus Copilot</h1>
      </div>
      <p className="text-base font-medium text-slate-500">학사 안내 키오스크</p>
    </header>
  );
}
