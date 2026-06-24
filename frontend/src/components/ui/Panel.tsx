import type { ComponentPropsWithoutRef } from "react";

const paddingClass = {
  sm: "p-4",
  md: "p-5",
  lg: "p-7",
} as const;

interface PanelProps extends ComponentPropsWithoutRef<"section"> {
  bordered?: boolean;
  padding?: keyof typeof paddingClass;
}

export function Panel({ bordered = false, children, className = "", padding = "sm", ...props }: PanelProps) {
  const borderClass = bordered ? "border border-slate-200 text-slate-950" : "";

  return (
    <section
      className={`rounded-lg bg-white shadow-sm ${borderClass} ${paddingClass[padding]} ${className}`.trim()}
      {...props}
    >
      {children}
    </section>
  );
}
