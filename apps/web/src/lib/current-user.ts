import { cookies } from "next/headers";
import type { Me } from "@/lib/api";

export async function loadMe(): Promise<Me | null> {
  const jar = await cookies();
  const header = jar
    .getAll()
    .map((item) => `${item.name}=${item.value}`)
    .join("; ");
  if (!header.includes("__Host-access=")) {
    return null;
  }
  const base = (process.env.API_INTERNAL_URL || process.env.API_URL || "http://localhost:8000").replace(
    /\/$/,
    "",
  );
  try {
    const response = await fetch(`${base}/api/v1/users/me`, {
      headers: { cookie: header, accept: "application/json" },
      cache: "no-store",
    });
    if (!response.ok) {
      return null;
    }
    return (await response.json()) as Me;
  } catch {
    return null;
  }
}
