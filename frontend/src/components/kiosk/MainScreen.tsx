import { useQuery } from "@tanstack/react-query";

import { fetchCategories } from "../../api/categories";
import { fetchFAQ } from "../../api/faq";
import { useChat } from "../../hooks/useChat";
import { useKioskStore } from "../../store/kioskStore";
import type { FAQItem } from "../../types/kiosk";
import { CategoryBar } from "./main/CategoryBar";
import { FAQGrid } from "./main/FAQGrid";
import { HeaderBar } from "./main/HeaderBar";
import { InputBar } from "./main/InputBar";

export function MainScreen() {
  const selectedCategory = useKioskStore((state) => state.selectedCategory);
  const setCategory = useKioskStore((state) => state.setCategory);
  const setMode = useKioskStore((state) => state.setMode);
  const { submit } = useChat();

  const categoriesQuery = useQuery({
    queryKey: ["kiosk-categories"],
    queryFn: fetchCategories,
  });
  const faqQuery = useQuery({
    queryKey: ["kiosk-faq", selectedCategory],
    queryFn: () => fetchFAQ(selectedCategory),
  });

  const categories = categoriesQuery.data ?? [];
  const faq = faqQuery.data ?? [];
  const openInputMode = () => setMode("input");
  const openVoiceEntry = () => {
    // Future STT integration should start from InputMode after HTTPS/browser support is verified.
    setMode("input");
  };
  const submitFAQ = (item: FAQItem) => {
    void submit(item.question);
  };

  return (
    <div className="flex h-screen flex-col bg-[#f6f8fc] text-slate-950">
      <HeaderBar />
      <CategoryBar categories={categories} onSelect={setCategory} selectedCategory={selectedCategory} />
      <FAQGrid faqs={faq} onSelect={submitFAQ} />
      <InputBar onFocus={openInputMode} onVoice={openVoiceEntry} />
    </div>
  );
}
