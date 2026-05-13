import { useEffect, useRef, useState } from "react";
import Hangul from "hangul-js";
import Keyboard from "react-simple-keyboard";
import "react-simple-keyboard/build/css/index.css";

interface VirtualKeyboardProps {
  value: string;
  onChange: (value: string) => void;
  onSubmit: () => void;
}

export function VirtualKeyboard({ value, onChange, onSubmit }: VirtualKeyboardProps) {
  const [layoutName, setLayoutName] = useState<"default" | "shift">("default");
  const keyboardRef = useRef<{ setInput: (input: string, inputName?: string, skipSync?: boolean) => void } | null>(null);

  useEffect(() => {
    keyboardRef.current?.setInput(Hangul.disassemble(value).join(""), "default", true);
  }, [value]);

  return (
    <section
      className={`kiosk-keyboard shrink-0 border-t border-slate-200 bg-white px-4 pb-6 pt-5 ${
        layoutName === "shift" ? "kiosk-keyboard-shift-on" : ""
      }`}
    >
      <Keyboard
        keyboardRef={(keyboard) => {
          keyboardRef.current = keyboard;
        }}
        layout={{
          default: [
            "ㅂ ㅈ ㄷ ㄱ ㅅ ㅛ ㅕ ㅑ ㅐ ㅔ",
            "ㅁ ㄴ ㅇ ㄹ ㅎ ㅗ ㅓ ㅏ ㅣ",
            "ㅋ ㅌ ㅊ ㅍ ㅠ ㅜ ㅡ {bksp}",
            "{shift} {space} {enter}",
          ],
          shift: [
            "ㅃ ㅉ ㄸ ㄲ ㅆ ㅛ ㅕ ㅑ ㅒ ㅖ",
            "ㅁ ㄴ ㅇ ㄹ ㅎ ㅗ ㅓ ㅏ ㅣ",
            "ㅋ ㅌ ㅊ ㅍ ㅠ ㅜ ㅡ {bksp}",
            "{shift} {space} {enter}",
          ],
        }}
        layoutName={layoutName}
        display={{
          "{bksp}": "Backspace",
          "{enter}": "Enter",
          "{shift}": "Shift",
          "{space}": "Space",
        }}
        onKeyPress={(button) => {
          if (button === "{shift}") {
            setLayoutName((current) => (current === "default" ? "shift" : "default"));
            return;
          }
          if (button === "{enter}" && value.trim()) onSubmit();
        }}
        onChange={(input) => onChange(Hangul.assemble(input.split("")))}
      />
    </section>
  );
}
