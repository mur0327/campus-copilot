import { beforeEach, describe, expect, it } from "vitest";

import { useKioskStore } from "./kioskStore";
import type { AnswerData } from "../types/kiosk";

const initialState = {
  mode: "main" as const,
  selectedCategory: null,
  currentQuery: "",
  answerData: null,
};

function makeAnswerData(overrides: Partial<AnswerData> = {}): AnswerData {
  return {
    answerability: "answerable",
    answer: "포털에서 신청합니다.",
    summary: "포털에서 신청합니다.",
    sources: [],
    procedureSteps: [],
    notes: [],
    limitations: [],
    conflictWarning: null,
    isStreaming: false,
    ...overrides,
  };
}

beforeEach(() => {
  useKioskStore.setState(initialState);
});

describe("kioskStore", () => {
  it("provides the initial kiosk state", () => {
    expect(useKioskStore.getState()).toMatchObject(initialState);
  });

  it("updates mode, category, current query, and answer data", () => {
    const answerData: AnswerData = makeAnswerData();

    useKioskStore.getState().setMode("input");
    useKioskStore.getState().setCategory("academic");
    useKioskStore.getState().setCurrentQuery("휴학 신청");
    useKioskStore.getState().setAnswerData(answerData);

    expect(useKioskStore.getState()).toMatchObject({
      mode: "input",
      selectedCategory: "academic",
      currentQuery: "휴학 신청",
      answerData,
    });
  });

  it("submitQuery stores the question and moves to answer mode", () => {
    useKioskStore.getState().submitQuery("등록금 납부 기간");

    expect(useKioskStore.getState().currentQuery).toBe("등록금 납부 기간");
    expect(useKioskStore.getState().mode).toBe("answer");
  });

  it("supports functional answer data updates", () => {
    useKioskStore.getState().setAnswerData(makeAnswerData({ answer: "휴학", summary: "휴학", isStreaming: true }));

    useKioskStore.getState().setAnswerData((prev) =>
      prev ? { ...prev, answer: `${prev.answer} 신청` } : prev,
    );

    expect(useKioskStore.getState().answerData?.answer).toBe("휴학 신청");
  });

  it("resetToMain restores main state", () => {
    useKioskStore.getState().setMode("answer");
    useKioskStore.getState().setCategory("academic");
    useKioskStore.getState().setCurrentQuery("휴학 신청");
    useKioskStore.getState().setAnswerData(makeAnswerData());

    useKioskStore.getState().resetToMain();

    expect(useKioskStore.getState()).toMatchObject(initialState);
  });
});
