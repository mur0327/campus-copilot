const sections = [
  "크롤 작업 상태",
  "문서 적재 현황",
  "충돌 탐지 목록",
  "질문 로그",
];

export default function AdminPage() {
  return (
    <main className="min-h-screen px-6 py-10 text-stone-50">
      <div className="mx-auto flex max-w-6xl flex-col gap-6">
        <header className="rounded-[2rem] border border-white/10 bg-white/6 px-8 py-7 backdrop-blur">
          <p className="text-sm font-medium uppercase tracking-[0.3em] text-sky-200/80">
            Admin
          </p>
          <h1 className="mt-3 text-4xl font-semibold text-white">운영자 화면</h1>
          <p className="mt-4 text-base leading-7 text-slate-300/80">
            워커 상태, 적재 문서, 충돌 쌍, 로그 목록이 들어올 영역을 미리 배치해 둔 스캐폴드입니다.
          </p>
        </header>

        <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
          {sections.map((section, index) => (
            <article
              key={section}
              className="rounded-[1.5rem] border border-white/10 bg-slate-950/35 p-5 shadow-[0_18px_50px_rgba(0,0,0,0.2)]"
            >
              <p className="text-xs uppercase tracking-[0.28em] text-slate-400">
                Panel {index + 1}
              </p>
              <h2 className="mt-4 text-2xl font-semibold text-white">{section}</h2>
              <p className="mt-3 text-sm leading-6 text-slate-300/75">
                API 연결 전 상태라 실제 데이터 대신 패널 자리만 잡아 두었습니다.
              </p>
            </article>
          ))}
        </section>
      </div>
    </main>
  );
}
