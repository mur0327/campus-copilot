import type { ButtonHTMLAttributes, ReactNode } from "react";

interface TileButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  icon: ReactNode;
}

export function TileButton({ children, className = "", icon, type = "button", ...props }: TileButtonProps) {
  return (
    <button
      className={`flex flex-col items-center justify-center gap-1.5 rounded-md bg-slate-100 py-3 font-semibold disabled:text-slate-400 ${className}`.trim()}
      type={type}
      {...props}
    >
      {icon}
      {children}
    </button>
  );
}
