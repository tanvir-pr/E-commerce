import { NextRequest, NextResponse } from "next/server";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

const HOP_BY_HOP = new Set([
  "connection",
  "keep-alive",
  "proxy-authenticate",
  "proxy-authorization",
  "te",
  "trailers",
  "transfer-encoding",
  "upgrade",
  "host",
  "content-length",
  "content-encoding",
]);

type RouteContext = { params: Promise<{ path: string[] }> };

function apiBase(): string {
  const raw = process.env.API_INTERNAL_URL || process.env.API_URL || "http://localhost:8000";
  return raw.replace(/\/$/, "");
}

function clientIp(request: NextRequest): string {
  const forwarded = request.headers.get("x-forwarded-for");
  if (forwarded) {
    const first = forwarded.split(",")[0]?.trim();
    if (first) {
      return first;
    }
  }
  return request.headers.get("x-real-ip") || "127.0.0.1";
}

async function proxy(request: NextRequest, context: RouteContext): Promise<NextResponse> {
  const { path } = await context.params;
  const target = `${apiBase()}/api/v1/${path.map((segment) => encodeURIComponent(segment)).join("/")}${request.nextUrl.search}`;
  const headers = new Headers();
  request.headers.forEach((value, key) => {
    if (!HOP_BY_HOP.has(key.toLowerCase())) {
      headers.set(key, value);
    }
  });
  headers.set("x-forwarded-for", clientIp(request));
  if (!headers.get("x-request-id")) {
    headers.set("x-request-id", crypto.randomUUID());
  }

  const method = request.method.toUpperCase();
  const hasBody = method !== "GET" && method !== "HEAD";

  try {
    const upstream = await fetch(target, {
      method,
      headers,
      body: hasBody ? await request.arrayBuffer() : undefined,
      redirect: "manual",
      cache: "no-store",
    });
    const responseHeaders = new Headers();
    upstream.headers.forEach((value, key) => {
      const lower = key.toLowerCase();
      if (lower !== "set-cookie" && !HOP_BY_HOP.has(lower)) {
        responseHeaders.set(key, value);
      }
    });
    const setCookies =
      typeof upstream.headers.getSetCookie === "function" ? upstream.headers.getSetCookie() : [];
    const response = new NextResponse(await upstream.arrayBuffer(), {
      status: upstream.status,
      headers: responseHeaders,
    });
    for (const cookie of setCookies) {
      response.headers.append("set-cookie", cookie);
    }
    return response;
  } catch {
    return NextResponse.json(
      {
        type: "https://store.local/problems/internal",
        title: "Bad Gateway",
        status: 502,
        detail: "The store API is unavailable.",
        request_id: headers.get("x-request-id"),
      },
      { status: 502, headers: { "content-type": "application/problem+json" } },
    );
  }
}

export function GET(request: NextRequest, context: RouteContext) {
  return proxy(request, context);
}

export function POST(request: NextRequest, context: RouteContext) {
  return proxy(request, context);
}

export function PUT(request: NextRequest, context: RouteContext) {
  return proxy(request, context);
}

export function PATCH(request: NextRequest, context: RouteContext) {
  return proxy(request, context);
}

export function DELETE(request: NextRequest, context: RouteContext) {
  return proxy(request, context);
}

export function HEAD(request: NextRequest, context: RouteContext) {
  return proxy(request, context);
}
