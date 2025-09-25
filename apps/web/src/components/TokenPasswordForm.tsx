"use client";

import { FormEvent, useState } from "react";
import { useLocale, useTranslations } from "next-intl";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Button } from "@/components/Button";
import { TextField } from "@/components/TextField";
import { apiPost, fetchCsrfToken } from "@/lib/api";
import { passwordPairSchema } from "@/lib/validation";

export function TokenPasswordForm({
  namespace,
  path,
}: {
  namespace: "reset" | "invite";
  path: string;
}) {
  const t = useTranslations(namespace);
  const locale = useLocale();
  const token = useSearchParams().get("token");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);
  const [pending, setPending] = useState(false);

  if (!token) {
    return (
      <p role="alert" className="text-base text-danger">
        {t("missing")}
      </p>
    );
  }

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    const parsed = passwordPairSchema({
      password: t("passwordShort"),
      confirm: t("passwordMismatch"),
    }).safeParse({ password, confirmPassword });
    if (!parsed.success) {
      const next: Record<string, string> = {};
      for (const issue of parsed.error.issues) {
        const key = String(issue.path[0] ?? "form");
        if (!next[key]) {
          next[key] = issue.message;
        }
      }
      setFieldErrors(next);
      return;
    }
    setFieldErrors({});
    setPending(true);
    try {
      const csrf = await fetchCsrfToken();
      const response = await apiPost(path, { token, password: parsed.data.password }, csrf);
      if (response.status === 400) {
        setError(t("invalid"));
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

  if (success) {
    return (
      <div className="flex flex-col gap-sm">
        <p role="status" className="text-base font-medium text-ok">
          {t("success")}
        </p>
        <Link className="font-semibold text-brand underline-offset-2 hover:underline" href={`/${locale}/login`}>
          {t("signIn")}
        </Link>
      </div>
    );
  }

  return (
    <form className="flex flex-col gap-md" noValidate onSubmit={(event) => void onSubmit(event)}>
      {error ? (
        <p role="alert" className="text-sm text-danger">
          {error}
        </p>
      ) : null}
      <TextField
        id="token-password"
        label={t("password")}
        type="password"
        autoComplete="new-password"
        value={password}
        error={fieldErrors.password}
        onChange={(event) => setPassword(event.target.value)}
      />
      <TextField
        id="token-confirm"
        label={t("confirmPassword")}
        type="password"
        autoComplete="new-password"
        value={confirmPassword}
        error={fieldErrors.confirmPassword}
        onChange={(event) => setConfirmPassword(event.target.value)}
      />
      <Button type="submit" pending={pending}>
        {pending ? t("submitting") : t("submit")}
      </Button>
    </form>
  );
}
