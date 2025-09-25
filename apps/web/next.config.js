const createNextIntlPlugin = require("next-intl/plugin");

const withNextIntl = createNextIntlPlugin("./src/i18n/request.ts");

/** @type {import('next').NextConfig} */
const nextConfig = {
  poweredByHeader: false,
  async rewrites() {
    // afterFiles (the default): a matching App Router handler wins.
    // apps/web/src/app/api/v1/[...path]/route.ts is the cookie-safe proxy.
    // This rewrite documents the same target and covers the path if the handler is absent.
    const base = process.env.API_INTERNAL_URL || process.env.API_URL || "http://localhost:8000";
    return [
      {
        source: "/api/v1/:path*",
        destination: `${base.replace(/\/$/, "")}/api/v1/:path*`,
      },
    ];
  },
};

module.exports = withNextIntl(nextConfig);
