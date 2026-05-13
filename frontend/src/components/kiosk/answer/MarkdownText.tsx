import Markdown, { type Components } from "react-markdown";

const answerMarkdownComponents: Components = {
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
};

const compactMarkdownComponents: Components = {
  ...answerMarkdownComponents,
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
    <ol className="my-2 list-decimal space-y-1 pl-5" {...props}>
      {children}
    </ol>
  ),
  p: ({ children, ...props }) => (
    <p className="my-1 whitespace-pre-wrap" {...props}>
      {children}
    </p>
  ),
  ul: ({ children, ...props }) => (
    <ul className="my-2 list-disc space-y-1 pl-5" {...props}>
      {children}
    </ul>
  ),
};

interface MarkdownTextProps {
  children: string;
  variant?: "answer" | "compact";
}

export function MarkdownText({ children, variant = "answer" }: MarkdownTextProps) {
  const components = variant === "compact" ? compactMarkdownComponents : answerMarkdownComponents;

  return <Markdown components={components}>{children}</Markdown>;
}
