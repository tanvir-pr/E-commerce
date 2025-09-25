export const routing = {
  locales: ["en"],
  defaultLocale: "en",
  localePrefix: "always",
} as const;

export type AppLocale = (typeof routing.locales)[number];
