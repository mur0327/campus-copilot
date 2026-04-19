const categories = [
  "입학",
  "장학",
  "수강신청",
  "학사일정",
  "증명서",
  "생활관",
];

export default function KioskPage() {
  return (
    <main className="flex min-h-screen items-center justify-center px-6 py-10 text-stone-50">
      <section className="grid w-full max-w-6xl gap-6 lg:grid-cols-[1.2fr_0.8fr]">
        <div className="overflow-hidden rounded-[2rem] border border-white/10 bg-white/6 shadow-[0_30px_80px_rgba(0,0,0,0.28)] backdrop-blur">
          <div className="border-b border-white/10 px-8 py-6">
            <p className="text-sm font-medium uppercase tracking-[0.35em] text-amber-200/80">
              Honam University
            </p>
            <h1 className="mt-3 text-4xl font-semibold tracking-tight text-white md:text-6xl">
              Campus Copilot
            </h1>
            <p className="mt-4 max-w-2xl text-base leading-7 text-slate-200/82 md:text-lg">
              공식 문서 기준으로 학사 안내를 바로 찾아드리는 키오스크 스캐폴드 화면입니다.
            </p>
          </div>

          <div className="grid gap-4 px-8 py-8 md:grid-cols-2">
            {categories.map((category) => (
              <button
                key={category}
                type="button"
                className="group rounded-[1.5rem] border border-white/10 bg-slate-950/30 px-5 py-5 text-left transition hover:-translate-y-1 hover:border-amber-300/50 hover:bg-amber-100/10"
              >
                <span className="text-xs font-semibold uppercase tracking-[0.28em] text-amber-200/75">
                  Category
                </span>
                <strong className="mt-3 block text-2xl font-semibold text-white">
                  {category}
                </strong>
                <span className="mt-2 block text-sm text-slate-300/75">
                  준비 중인 질의 응답 진입점
                </span>
              </button>
            ))}
          </div>
        </div>

        <aside className="flex flex-col justify-between rounded-[2rem] border border-white/10 bg-slate-950/45 p-8 shadow-[0_24px_60px_rgba(0,0,0,0.25)]">
          <div>
            <p className="text-sm font-medium uppercase tracking-[0.3em] text-emerald-200/80">
              Preview
            </p>
            <h2 className="mt-3 text-3xl font-semibold text-white">실시간 안내 준비 중</h2>
            <p className="mt-4 text-base leading-7 text-slate-300/80">
              다음 단계에서 질문 입력, 출처 표시, 절차 안내, 충돌 경고 UI가 여기에 연결됩니다.
            </p>
          </div>

          <div className="mt-10 rounded-[1.5rem] border border-emerald-300/20 bg-emerald-300/10 p-5">
            <p className="text-sm uppercase tracking-[0.28em] text-emerald-100/75">Status</p>
            <p className="mt-3 text-lg font-medium text-white">Frontend scaffold ready</p>
            <p className="mt-2 text-sm text-emerald-50/75">
              React Router, React Query, Tailwind, Vite 기반 초기 화면
            </p>
          </div>
        </aside>
      </section>
    </main>
  );
}
