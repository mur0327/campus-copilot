import { create } from "zustand";

import type { AnswerData, KioskMode } from "../types/kiosk";

type AnswerDataUpdater = AnswerData | null | ((prev: AnswerData | null) => AnswerData | null);

interface KioskStore {
  mode: KioskMode;
  selectedCategory: string | null;
  currentQuery: string;
  answerData: AnswerData | null;
  setMode: (mode: KioskMode) => void;
  setCategory: (categoryId: string | null) => void;
  setCurrentQuery: (query: string) => void;
  submitQuery: (query: string) => void;
  setAnswerData: (data: AnswerDataUpdater) => void;
  resetToMain: () => void;
}

const initialState = {
  mode: "main" as const,
  selectedCategory: null,
  currentQuery: "",
  answerData: null,
};

export const useKioskStore = create<KioskStore>((set) => ({
  ...initialState,
  setMode: (mode) => set({ mode }),
  setCategory: (selectedCategory) => set({ selectedCategory }),
  setCurrentQuery: (currentQuery) => set({ currentQuery }),
  submitQuery: (query) => set({ currentQuery: query, mode: "answer" }),
  setAnswerData: (data) =>
    set((state) => ({
      answerData: typeof data === "function" ? data(state.answerData) : data,
    })),
  resetToMain: () => {
    // Future TTS integration should stop active speech here before clearing state.
    set(initialState);
  },
}));
