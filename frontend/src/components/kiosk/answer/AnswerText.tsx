interface AnswerTextProps {
  text: string;
  isStreaming: boolean;
}

export function AnswerText({ text, isStreaming }: AnswerTextProps) {
  return (
    <p className="mt-5 whitespace-pre-wrap text-2xl leading-relaxed">
      {text || "답변을 준비하고 있습니다."}
      {isStreaming ? (
        <span className="ml-1 animate-pulse" data-testid="streaming-cursor">
          |
        </span>
      ) : null}
    </p>
  );
}
