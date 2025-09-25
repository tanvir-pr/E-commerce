"use client";

import { useEffect, useState } from "react";
import { useLocale, useTranslations } from "next-intl";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { apiPost, fetchCsrfToken } from "@/lib/api";

const inflight = new Map<string, Promise<"success" | "error">>();

function verifyOnce(token: string): Promise<"success" | "error"> {
  const existing = inflight.get(token);
  if (existing) {
    return existing;
  }
  const promise = (async () => {
    try {
      const csrf = await fetchCsrfToken();
      const response = await apiPost("/api/v1/auth/verify-email", { token }, csrf);
      return response.ok ? "success" : "error";
    } catch {
      return "error";
    }
  })();
  inflight.set(token, promise);
  return promise;
}

export function VerifyEmail() {
  const t = useTranslations("verify");
  const locale = useLocale();
  const token = useSearchParams().get("token");
  const [state, setState] = useState<"checking" | "success" | "error">("checking");

  useEffect(() => {
    if (!token) {
      setState("error");
      return;
    }
    let active = true;
    void verifyOnce(token).then((result) => {
      if (active) {
        setState(result);
      }
    });
    return () => {
      active = false;
    };
  }, [token]);

  if (!token) {
    if (state === "checking") {
      return (
        <p role="status" className="text-base text-muted">
          {t("checking")}
        </p>
      );
    }
    return (
      <p role="alert" className="text-base text-danger">
        {t("missing")}
      </p>
    );
  }

  if (state === "checking") {
    return (
      <p role="status" className="text-base text-muted">
        {t("checking")}
      </p>
    );
  }

  if (state === "success") {
    return (
      <div className="flex flex-col gap-sm">
        <p role="status" className="text-base font-medium text-ok">
          {t("success")}
        </p>
        <Link
          className="inline-flex min-h-tap items-center font-semibold text-brand underline-offset-2 hover:underline"
          href={`/${locale}/login`}
        >
          {t("signIn")}
        </Link>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-sm">
      <p role="alert" className="text-base text-danger">
        {t("error")}
      </p>
      <Link
        className="inline-flex min-h-tap items-center font-semibold text-brand underline-offset-2 hover:underline"
        href={`/${locale}`}
      >
        {t("home")}
      </Link>
    </div>
  );
}
