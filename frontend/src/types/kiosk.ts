export type KioskMode = "main" | "input" | "answer";

export interface Category {
  id: string;
  name: string;
}

export interface FAQItem {
  id: string;
  question: string;
  category_id: string;
  priority?: number;
}

export interface PopularItem {
  rank: number;
  question: string;
  view_count: number;
}

export type SourceFreshness = "recent" | "stale";

export interface Source {
  title: string;
  url: string;
  crawled_at: string;
  freshness: SourceFreshness;
  chunk_id?: string;
}

export interface ConflictWarning {
  exists: boolean;
  description?: string;
}

export interface AnswerData {
  answer: string;
  sources: Source[];
  procedureSteps: string[];
  conflictWarning: ConflictWarning | null;
  isStreaming: boolean;
}

export interface ChatRequestPayload {
  question: string;
  category?: string | null;
}

export interface ChatResponsePayload {
  answer: string;
  sources: ChatSourcePayload[];
  procedure_steps: string[];
  conflict_warning: ConflictWarning;
  freshness: string;
  retrieval_status?: RetrievalStatusPayload;
}

export interface ChatSourcePayload {
  title: string;
  url: string;
  crawled_at: string;
  freshness?: SourceFreshness;
  chunk_id?: string;
}

export interface ChatMetadataPayload {
  sources?: ChatSourcePayload[];
  procedure_steps?: string[];
  conflict_warning?: ConflictWarning;
  freshness?: string;
  retrieval_status?: RetrievalStatusPayload;
}

export interface RetrievalStatusPayload {
  mode: "hybrid" | "semantic_only" | "keyword_only" | "empty" | string;
  degraded: boolean;
  semantic_available: boolean;
  bm25_available: boolean;
  semantic_error?: string | null;
  bm25_error?: string | null;
}

export interface ChatTokenPayload {
  text: string;
}

export interface ChatProcedureStepsPayload {
  procedure_steps: string[];
}

export interface ChatErrorPayload {
  message: string;
  retryable: boolean;
}

export type ChatSSEEvent =
  | {
      type: "metadata";
      sources: Source[];
      freshness: SourceFreshness;
      conflict_warning: ConflictWarning;
    }
  | { type: "token"; text: string }
  | { type: "procedure_steps"; procedure_steps: string[] }
  | { type: "done"; payload: ChatResponsePayload }
  | { type: "error"; message: string; retryable: boolean };

export type ChatResponseToAnswerDataMapper = (payload: ChatResponsePayload) => AnswerData;

export function normalizeSourceFreshness(value: string): SourceFreshness {
  if (value === "recent" || value === "stale") {
    return value;
  }

  console.warn(`Unknown source freshness "${value}", treating as stale.`);
  return "stale";
}

export const mapChatResponseToAnswerData: ChatResponseToAnswerDataMapper = (payload) => {
  const freshness = normalizeSourceFreshness(payload.freshness);

  return {
    answer: payload.answer,
    sources: payload.sources.map(({ title, url, crawled_at, freshness: sourceFreshness, chunk_id }) => ({
      title,
      url,
      crawled_at,
      freshness: sourceFreshness ? normalizeSourceFreshness(sourceFreshness) : freshness,
      chunk_id,
    })),
    procedureSteps: payload.procedure_steps,
    conflictWarning: payload.conflict_warning,
    isStreaming: false,
  };
};
