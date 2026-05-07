import Markdown from "react-markdown";

interface AnswerTextProps {
  text: string;
  isStreaming: boolean;
}

export function AnswerText({ text, isStreaming }: AnswerTextProps) {
  const displayText = text || "답변을 준비하고 있습니다.";

  return (
    <div className="mt-5 text-2xl leading-relaxed">
      <Markdown
        components={{
          a: ({ children, ...props }) => (
            <a className="font-semibold text-blue-700 underline" rel="noreferrer" target="_blank" {...props}>
              {children}
            </a>
          ),
          li: ({ children, ...props }) => (
            <li className="pl-1" {...props}>
              {children}
            </li>
          ),
          ol: ({ children, ...props }) => (
            <ol className="my-3 list-decimal space-y-2 pl-7" {...props}>
              {children}
            </ol>
          ),
          p: ({ children, ...props }) => (
            <p className="my-3 whitespace-pre-wrap" {...props}>
              {children}
            </p>
          ),
          strong: ({ children, ...props }) => (
            <strong className="font-bold text-slate-950" {...props}>
              {children}
            </strong>
          ),
          ul: ({ children, ...props }) => (
            <ul className="my-3 list-disc space-y-2 pl-7" {...props}>
              {children}
            </ul>
          ),
        }}
      >
        {displayText}
      </Markdown>
      {isStreaming ? (
        <span className="ml-1 animate-pulse" data-testid="streaming-cursor">
          |
        </span>
      ) : null}
    </div>
  );
}
