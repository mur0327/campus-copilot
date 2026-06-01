import { MarkdownText } from "./MarkdownText";

interface AnswerTextProps {
  text: string;
  isStreaming: boolean;
  statusMessage?: string;
}

export function AnswerText({ text, isStreaming, statusMessage }: AnswerTextProps) {
  const displayText = text || statusMessage || "답변을 준비하고 있습니다.";

  if (!text && isStreaming) {
    return (
      <div className="mt-5 text-2xl leading-relaxed">
        <p className="answer-loading-shimmer my-3 whitespace-pre-wrap" data-testid="answer-loading-text">
          {displayText}
        </p>
      </div>
    );
  }

  return (
    <div className="mt-5 text-2xl leading-relaxed">
      <MarkdownText>{displayText}</MarkdownText>
    </div>
  );
}
