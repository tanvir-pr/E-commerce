export type Health = {
  status: "ok" | "down";
  db: "ok" | "down";
  redis: "ok" | "down";
};

export type Me = {
  id: string;
  email: string | null;
  email_verified_at: string | null;
  phone: string | null;
  phone_verified_at: string | null;
  name: string | null;
  roles: string[];
  totp_enabled: boolean;
};

export type AuthConfig = {
  phone_registration_enabled: boolean;
};

export type LoginNext = "session" | "enroll" | "challenge";

export type SessionInfo = {
  family_id: string;
  created_at: string;
  expires_at: string;
  current: boolean;
};

export type AuditEvent = {
  id: string;
  actor_id: string | null;
  actor_email: string | null;
  action: string;
  entity_type: string;
  entity_id: string | null;
  created_at: string;
};

export type TotpSetup = {
  otpauth_uri: string;
  secret: string;
  qr_svg: string;
};

export async function fetchCsrfToken(): Promise<string> {
  const response = await fetch("/api/v1/auth/csrf", {
    method: "GET",
    credentials: "include",
    headers: { Accept: "application/json" },
    cache: "no-store",
  });
  if (!response.ok) {
    throw new Error("csrf");
  }
  const body = (await response.json()) as { token?: string };
  if (!body.token) {
    throw new Error("csrf");
  }
  return body.token;
}

export async function apiSend(
  method: "POST" | "PATCH" | "PUT" | "DELETE",
  path: string,
  payload: unknown,
  csrf: string,
): Promise<Response> {
  return fetch(path, {
    method,
    credentials: "include",
    headers: {
      Accept: "application/json",
      "Content-Type": "application/json",
      "X-CSRF-Token": csrf,
    },
    body: JSON.stringify(payload ?? {}),
    cache: "no-store",
  });
}

export async function apiPost(path: string, payload: unknown, csrf: string): Promise<Response> {
  return apiSend("POST", path, payload, csrf);
}

export async function apiGet(path: string): Promise<Response> {
  return fetch(path, {
    method: "GET",
    credentials: "include",
    headers: { Accept: "application/json" },
    cache: "no-store",
  });
}

export async function fetchHealth(): Promise<Health | null> {
  try {
    const response = await fetch("/api/v1/health", { cache: "no-store", credentials: "include" });
    if (!response.ok) {
      return null;
    }
    const body = (await response.json()) as Health;
    return body.status === "ok" ? body : null;
  } catch {
    return null;
  }
}

export async function fetchMe(): Promise<Me | null> {
  try {
    const response = await apiGet("/api/v1/users/me");
    if (!response.ok) {
      return null;
    }
    return (await response.json()) as Me;
  } catch {
    return null;
  }
}

export async function fetchAuthConfig(): Promise<AuthConfig> {
  try {
    const response = await apiGet("/api/v1/auth/config");
    if (!response.ok) {
      return { phone_registration_enabled: false };
    }
    const body = (await response.json()) as Partial<AuthConfig>;
    return { phone_registration_enabled: body.phone_registration_enabled === true };
  } catch {
    return { phone_registration_enabled: false };
  }
}
