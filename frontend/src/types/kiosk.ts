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
export type Answerability = "answerable" | "partial" | "insufficient";
export type ChatStatusStep = "retrieving" | "checking_evidence" | "generating" | "validating";

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
  answerability: Answerability;
  answer: string;
  summary: string;
  sources: Source[];
  procedureSteps: string[];
  notes: string[];
  limitations: string[];
  conflictWarning: ConflictWarning | null;
  isStreaming: boolean;
  statusMessage?: string;
}

export interface ChatRequestPayload {
  question: string;
  category?: string | null;
}

export interface ChatResponsePayload {
  answerability: Answerability;
  answer: string;
  summary: string;
  sources: ChatSourcePayload[];
  procedure_steps: string[];
  notes: string[];
  limitations: string[];
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
  evidence_candidate_count?: number;
  display_source_count?: number;
  answerability?: Answerability;
}

export interface ChatStatusPayload {
  step: ChatStatusStep;
}

export interface ChatErrorPayload {
  message: string;
  retryable: boolean;
}

export type ChatSSEEvent =
  | { type: "status"; step: ChatStatusStep }
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
    answerability: payload.answerability,
    answer: payload.answer,
    summary: payload.summary,
    sources: payload.sources.map(({ title, url, crawled_at, freshness: sourceFreshness, chunk_id }) => ({
      title,
      url,
      crawled_at,
      freshness: sourceFreshness ? normalizeSourceFreshness(sourceFreshness) : freshness,
      chunk_id,
    })),
    procedureSteps: payload.procedure_steps,
    notes: payload.notes,
    limitations: payload.limitations,
    conflictWarning: payload.conflict_warning,
    isStreaming: false,
  };
};
