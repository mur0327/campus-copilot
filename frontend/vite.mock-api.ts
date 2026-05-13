import type { IncomingMessage, ServerResponse } from "node:http";
import type { Plugin } from "vite";

import { fallbackCategories, fallbackFAQForCategory, fallbackPopular } from "./src/api/mockKioskData";

function sendJson(res: ServerResponse, statusCode: number, payload: unknown): void {
  res.statusCode = statusCode;
  res.setHeader("Content-Type", "application/json; charset=utf-8");
  res.end(JSON.stringify(payload));
}

function sendSse(res: ServerResponse, events: Array<{ event: string; data: unknown }>): void {
  res.statusCode = 200;
  res.setHeader("Content-Type", "text/event-stream; charset=utf-8");
  res.setHeader("Cache-Control", "no-cache");
  res.setHeader("Connection", "keep-alive");

  for (const event of events) {
    res.write(`event: ${event.event}\n`);
    res.write(`data: ${JSON.stringify(event.data)}\n\n`);
  }

  res.end();
}

function readRequestBody(req: IncomingMessage): Promise<string> {
  return new Promise((resolve, reject) => {
    const chunks: Buffer[] = [];

    req.on("data", (chunk) => chunks.push(Buffer.from(chunk)));
    req.on("end", () => resolve(Buffer.concat(chunks).toString("utf8")));
    req.on("error", reject);
  });
}

async function readQuestion(req: IncomingMessage): Promise<string> {
  try {
    const body = await readRequestBody(req);
    const payload = JSON.parse(body || "{}") as { question?: string };
    return payload.question?.trim() || "학사 안내";
  } catch {
    return "학사 안내";
  }
}

function buildChatPayload(question: string) {
  const procedureSteps = getMockProcedureSteps(question);

  return {
    answer: `${question}에 대한 개발용 mock 답변입니다. 실제 학사 데이터가 아니라 프론트 화면 확인용 응답입니다. 답변 영역에는 확인된 사실과 안내 문장을 두고, 아래 절차 영역에는 사용자가 이어서 할 일을 분리해 표시합니다.`,
    sources: [
      {
        title: "호남대학교 학사안내 mock",
        url: "https://www.honam.ac.kr",
        crawled_at: "2026-05-10",
        freshness: "recent",
        chunk_id: "mock-source-1",
      },
    ],
    procedure_steps: procedureSteps,
    conflict_warning: { exists: false },
    freshness: "recent",
  };
}

function getMockProcedureSteps(question: string): string[] {
  if (question.includes("휴학")) {
    return ["포털에 로그인한 뒤 학적 변동 메뉴를 엽니다.", "휴학 신청서를 작성하고 사유를 선택합니다.", "지도교수 또는 학과 승인 상태를 확인합니다."];
  }

  if (question.includes("증명서")) {
    return ["증명 발급 메뉴에서 필요한 증명서를 선택합니다.", "발급 언어와 매수를 확인합니다.", "온라인 출력 또는 방문 수령 방식을 선택합니다."];
  }

  if (question.includes("등록금")) {
    return ["등록금 고지서와 납부 기간을 확인합니다.", "가상계좌 또는 지정 납부 방법을 선택합니다.", "납부 후 포털에서 수납 상태를 확인합니다."];
  }

  if (question.includes("장학")) {
    return ["장학 공지에서 신청 대상과 제출 서류를 확인합니다.", "신청 기간 안에 포털 또는 담당 부서로 접수합니다.", "심사 결과와 지급 일정을 다시 확인합니다."];
  }

  return ["공식 안내의 대상과 기간을 먼저 확인합니다.", "필요한 서류나 담당 부서를 확인합니다.", "처리 상태를 포털 또는 담당 부서에서 다시 확인합니다."];
}

export function mockKioskApiPlugin(): Plugin {
  return {
    name: "campus-copilot-mock-kiosk-api",
    configureServer(server) {
      server.middlewares.use(async (req, res, next) => {
        if (!req.url) {
          next();
          return;
        }

        const url = new URL(req.url, "http://localhost");

        if (req.method === "GET" && url.pathname === "/api/v1/categories") {
          sendJson(res, 200, fallbackCategories);
          return;
        }

        if (req.method === "GET" && url.pathname === "/api/v1/faq") {
          sendJson(res, 200, fallbackFAQForCategory(url.searchParams.get("category")));
          return;
        }

        if (req.method === "GET" && url.pathname === "/api/v1/popular") {
          sendJson(res, 200, fallbackPopular);
          return;
        }

        if (req.method === "POST" && url.pathname === "/api/v1/chat") {
          const question = await readQuestion(req);
          const payload = buildChatPayload(question);

          if (req.headers.accept?.includes("text/event-stream")) {
            sendSse(res, [
              {
                event: "metadata",
                data: {
                  sources: payload.sources,
                  procedure_steps: payload.procedure_steps,
                  conflict_warning: payload.conflict_warning,
                  freshness: payload.freshness,
                },
              },
              { event: "token", data: { text: payload.answer } },
              { event: "procedure_steps", data: { procedure_steps: payload.procedure_steps } },
              { event: "done", data: payload },
            ]);
            return;
          }

          sendJson(res, 200, payload);
          return;
        }

        next();
      });
    },
  };
}
