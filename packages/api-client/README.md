# API client

Generated TypeScript types for the Store API. The web app still calls the API with `fetch` from `apps/web/src/lib/api.ts`.

Regenerate while the API is running:

```powershell
cd D:\Full-web-4-project
corepack pnpm dlx openapi-typescript@7.6.1 http://localhost:8000/openapi.json -o packages/api-client/src/schema.ts
```

`src/schema.ts` is the generated output. `src/index.ts` re-exports `paths`, `components`, and `operations`.
