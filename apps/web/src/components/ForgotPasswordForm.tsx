"use client";

import { FormEvent, useState } from "react";
import { useLocale, useTranslations } from "next-intl";
import Link from "next/link";
import { Button } from "@/components/Button";
import { TextField } from "@/components/TextField";
import { apiPost, fetchCsrfToken } from "@/lib/api";
import { loginSchema } from "@/lib/validation";

export function ForgotPasswordForm() {
  const t = useTranslations("forgot");
  const locale = useLocale();
  const [email, setEmail] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [fieldError, setFieldError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);
  const [pending, setPending] = useState(false);

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSuccess(false);
    setError(null);
    const parsed = loginSchema({ email: t("emailInvalid"), password: "x" }).safeParse({
      email,
      password: "placeholder",
    });
    if (!parsed.success) {
      setFieldError(parsed.error.issues[0]?.message ?? t("emailInvalid"));
      return;
    }
    setFieldError(null);
    setPending(true);
    try {
      const csrf = await fetchCsrfToken();
      const response = await apiPost("/api/v1/auth/forgot-password", { email: parsed.data.email }, csrf);
      if (response.status === 429) {
        setError(t("rateLimited"));
        return;
      }
      if (!response.ok) {
        setError(t("genericError"));
        return;
      }
      setSuccess(true);
    } catch {
      setError(t("genericError"));
    } finally {
      setPending(false);
    }
  }

  return (
    <form className="flex flex-col gap-md" noValidate onSubmit={(event) => void onSubmit(event)}>
      {success ? (
        <p role="status" className="text-sm font-medium text-ok">
          {t("success")}
        </p>
      ) : null}
      {error ? (
        <p role="alert" className="text-sm text-danger">
          {error}
        </p>
      ) : null}
      <TextField
        id="forgot-email"
        label={t("email")}
        type="email"
        autoComplete="email"
        value={email}
        error={fieldError ?? undefined}
        onChange={(event) => setEmail(event.target.value)}
      />
      <Button type="submit" pending={pending}>
        {pending ? t("submitting") : t("submit")}
      </Button>
      <Link className="text-sm font-semibold text-brand underline-offset-2 hover:underline" href={`/${locale}/login`}>
        {t("back")}
      </Link>
    </form>
  );
}
