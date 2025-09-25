"use client";

import { FormEvent, useState } from "react";
import { useLocale, useTranslations } from "next-intl";
import { useRouter } from "next/navigation";
import { Button } from "@/components/Button";
import { TextField } from "@/components/TextField";
import { apiPost, fetchCsrfToken } from "@/lib/api";
import { codeSchema } from "@/lib/validation";

export function ChallengeForm() {
  const t = useTranslations("challenge");
  const locale = useLocale();
  const router = useRouter();
  const [code, setCode] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [fieldError, setFieldError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
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
      const response = await apiPost("/api/v1/auth/totp/challenge", { code: parsed.data.code }, csrf);
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
      router.push(`/${locale}`);
      router.refresh();
    } catch {
      setError(t("genericError"));
    } finally {
      setPending(false);
    }
  }

  return (
    <form className="flex flex-col gap-md" noValidate onSubmit={(event) => void onSubmit(event)}>
      {error ? (
        <p role="alert" className="text-sm text-danger">
          {error}
        </p>
      ) : null}
      <TextField
        id="challenge-code"
        label={t("code")}
        autoComplete="one-time-code"
        value={code}
        error={fieldError ?? undefined}
        onChange={(event) => setCode(event.target.value)}
      />
      <Button type="submit" pending={pending}>
        {pending ? t("submitting") : t("submit")}
      </Button>
    </form>
  );
}
