FROM node:22-bookworm-slim

ENV NEXT_TELEMETRY_DISABLED=1 \
    API_INTERNAL_URL=http://api:8000 \
    API_URL=http://api:8000

WORKDIR /app

RUN corepack enable && corepack prepare pnpm@9.15.4 --activate

COPY package.json pnpm-workspace.yaml pnpm-lock.yaml ./
COPY apps/web/package.json apps/web/package.json
COPY packages/api-client/package.json packages/api-client/package.json

RUN pnpm install --frozen-lockfile

COPY apps/web apps/web
COPY packages/api-client packages/api-client

RUN pnpm --filter web build

EXPOSE 3000

CMD ["pnpm", "--filter", "web", "start"]
