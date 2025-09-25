import type { ReactNode } from "react";

export function PageShell({
  title,
  lede,
  children,
  wide = false,
}: {
  title: string;
  lede?: string;
  children: ReactNode;
  wide?: boolean;
}) {
  const width = wide ? "max-w-3xl" : "max-w-lg";
  return (
    <main id="main" className={`mx-auto w-full px-md py-2xl ${width}`}>
      <h1 className="text-3xl font-semibold tracking-tight text-ink">{title}</h1>
      {lede ? <p className="mt-xs text-base text-muted">{lede}</p> : null}
      <div className="mt-lg rounded-lg border border-line bg-surface p-lg shadow-sm">{children}</div>
    </main>
  );
}
