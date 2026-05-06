import { useEffect, useRef } from "react";
import Hangul from "hangul-js";
import Keyboard from "react-simple-keyboard";
import "react-simple-keyboard/build/css/index.css";

interface VirtualKeyboardProps {
  value: string;
  onChange: (value: string) => void;
  onSubmit: () => void;
}

export function VirtualKeyboard({ value, onChange, onSubmit }: VirtualKeyboardProps) {
  const keyboardRef = useRef<{ setInput: (input: string, inputName?: string, skipSync?: boolean) => void } | null>(null);

  useEffect(() => {
    keyboardRef.current?.setInput(Hangul.disassemble(value).join(""), "default", true);
  }, [value]);

  return (
    <section className="shrink-0 border-t border-slate-200 bg-white p-4">
      <Keyboard
        keyboardRef={(keyboard) => {
          keyboardRef.current = keyboard;
        }}
        layout={{
          default: [
            "ㅂ ㅈ ㄷ ㄱ ㅅ ㅛ ㅕ ㅑ ㅐ ㅔ",
            "ㅁ ㄴ ㅇ ㄹ ㅎ ㅗ ㅓ ㅏ ㅣ",
            "ㅋ ㅌ ㅊ ㅍ ㅠ ㅜ ㅡ {bksp}",
            "{space} {enter}",
          ],
        }}
        onKeyPress={(button) => {
          if (button === "{enter}" && value.trim()) onSubmit();
        }}
        onChange={(input) => onChange(Hangul.assemble(input.split("")))}
      />
    </section>
  );
}
