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
  sources: Array<{
    title: string;
    url: string;
    crawled_at: string;
  }>;
  procedure_steps: string[];
  conflict_warning: ConflictWarning;
  freshness: string;
}

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
    sources: payload.sources.map((source) => ({
      ...source,
      freshness,
    })),
    procedureSteps: payload.procedure_steps,
    conflictWarning: payload.conflict_warning,
    isStreaming: false,
  };
};
