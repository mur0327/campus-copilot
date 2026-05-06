import { useQuery } from "@tanstack/react-query";
import { useState } from "react";

import { fetchPopular } from "../../api/popular";
import { useChat } from "../../hooks/useChat";
import { useKioskStore } from "../../store/kioskStore";
import { PopularList } from "./input/PopularList";
import { SearchBar } from "./input/SearchBar";
import { VirtualKeyboard } from "./input/VirtualKeyboard";

export function InputMode() {
  const [value, setValue] = useState("");
  const [voiceNotice, setVoiceNotice] = useState(false);
  const setMode = useKioskStore((state) => state.setMode);
  const { submit } = useChat();
  const popularQuery = useQuery({
    queryKey: ["kiosk-popular"],
    queryFn: fetchPopular,
  });

  const canSubmit = value.trim().length > 0;

  const submitValue = () => {
    if (canSubmit) void submit(value.trim());
  };

  const showVoicePlaceholder = () => {
    // Future STT integration starts here after HTTPS/browser support is verified.
    setVoiceNotice(true);
  };

  return (
    <div className="flex h-screen flex-col bg-[#f6f8fc] text-slate-950">
      <SearchBar
        onBack={() => setMode("main")}
        onChange={setValue}
        onSubmit={submitValue}
        onVoice={showVoicePlaceholder}
        value={value}
      />
      {voiceNotice ? (
        <p className="border-b border-slate-200 bg-white px-8 py-3 text-sm text-slate-500">
          음성 입력은 추후 운영 환경에서 사용할 예정입니다.
        </p>
      ) : null}

      <PopularList items={popularQuery.data ?? []} onSelect={setValue} />
      <VirtualKeyboard onChange={setValue} onSubmit={submitValue} value={value} />
    </div>
  );
}
