import type { ButtonHTMLAttributes, ReactNode } from "react";

export function Button({
  children,
  pending = false,
  ...props
}: {
  children: ReactNode;
  pending?: boolean;
} & ButtonHTMLAttributes<HTMLButtonElement>) {
  return (
    <button
      {...props}
      disabled={pending || props.disabled}
      className="inline-flex min-h-tap w-full items-center justify-center rounded-md bg-brand px-md text-base font-semibold text-brand-foreground hover:bg-brand-pressed disabled:cursor-not-allowed disabled:opacity-60"
    >
      {children}
    </button>
  );
}
