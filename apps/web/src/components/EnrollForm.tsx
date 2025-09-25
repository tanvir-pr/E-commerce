"use client";

import { FormEvent, useState } from "react";
import { useLocale, useTranslations } from "next-intl";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Button } from "@/components/Button";
import { TextField } from "@/components/TextField";
import { apiPost, fetchCsrfToken, type TotpSetup } from "@/lib/api";
import { codeSchema } from "@/lib/validation";

export function EnrollForm() {
  const t = useTranslations("enroll");
  const locale = useLocale();
  const router = useRouter();
  const [setup, setSetup] = useState<TotpSetup | null>(null);
  const [codes, setCodes] = useState<string[] | null>(null);
  const [code, setCode] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [fieldError, setFieldError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  async function start() {
    setError(null);
    setPending(true);
    try {
      const csrf = await fetchCsrfToken();
      const response = await apiPost("/api/v1/auth/totp/setup", {}, csrf);
      if (response.status === 401) {
        setError(t("signedOut"));
        return;
      }
      if (response.status === 429) {
        setError(t("rateLimited"));
        return;
      }
      if (!response.ok) {
        setError(t("genericError"));
        return;
      }
      setSetup((await response.json()) as TotpSetup);
    } catch {
      setError(t("genericError"));
    } finally {
      setPending(false);
    }
  }

  async function confirm(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    const parsed = codeSchema(t("codeInvalid")).safeParse({ code });
    if (!parsed.success) {
      setFieldError(parsed.error.issues[0]?.message ?? t("codeInvalid"));
      return;
    }
    setFieldError(null);
    setPending(true);
    try {
      const csrf = await fetchCsrfToken();
      const response = await apiPost("/api/v1/auth/totp/confirm", { code: parsed.data.code }, csrf);
      if (response.status === 401) {
        setError(t("invalid"));
        return;
      }
      if (response.status === 429) {
        setError(t("rateLimited"));
        return;
      }
      if (!response.ok) {
        setError(t("genericError"));
        return;
      }
      const body = (await response.json()) as { recovery_codes?: string[] };
      setCodes(body.recovery_codes ?? []);
    } catch {
      setError(t("genericError"));
    } finally {
      setPending(false);
    }
  }

  if (codes) {
    return (
      <div className="flex flex-col gap-md">
        <h2 className="text-lg font-semibold text-ink">{t("recoveryTitle")}</h2>
        <p className="text-sm text-muted">{t("recoveryLede")}</p>
        <ul className="grid grid-cols-2 gap-sm font-mono text-sm text-ink">
          {codes.map((item) => (
            <li key={item}>{item}</li>
          ))}
        </ul>
        <Button
          type="button"
          onClick={() => {
            router.push(`/${locale}`);
            router.refresh();
          }}
        >
          {t("continue")}
        </Button>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-md">
      {error ? (
        <p role="alert" className="text-sm text-danger">
          {error}
        </p>
      ) : null}
      {error === t("signedOut") ? (
        <Link className="font-semibold text-brand underline-offset-2 hover:underline" href={`/${locale}/login`}>
          {t("signIn")}
        </Link>
      ) : null}
      {!setup ? (
        <Button type="button" pending={pending} onClick={() => void start()}>
          {pending ? t("starting") : t("start")}
        </Button>
      ) : (
        <form className="flex flex-col gap-md" onSubmit={(event) => void confirm(event)}>
          {/* One-time SVG from the API. next/image does not optimize data URIs. */}
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            alt={t("qrAlt")}
            className="h-40 w-40"
            src={`data:image/svg+xml;charset=utf-8,${encodeURIComponent(setup.qr_svg)}`}
          />
          <p className="text-sm font-medium text-ink">{t("secretLabel")}</p>
          <p className="break-all font-mono text-sm text-ink">{setup.secret}</p>
          <p className="text-sm font-medium text-ink">{t("uriLabel")}</p>
          <p className="break-all text-sm text-muted">{setup.otpauth_uri}</p>
          <TextField
            id="enroll-code"
            label={t("code")}
            autoComplete="one-time-code"
            value={code}
            error={fieldError ?? undefined}
            onChange={(event) => setCode(event.target.value)}
          />
          <Button type="submit" pending={pending}>
            {pending ? t("confirming") : t("confirm")}
          </Button>
        </form>
      )}
    </div>
  );
}
