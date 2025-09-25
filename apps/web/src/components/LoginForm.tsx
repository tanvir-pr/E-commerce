"use client";

import { FormEvent, useEffect, useState } from "react";
import { useLocale, useTranslations } from "next-intl";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Button } from "@/components/Button";
import { TextField } from "@/components/TextField";
import { apiPost, fetchAuthConfig, fetchCsrfToken, type LoginNext } from "@/lib/api";
import { loginSchema } from "@/lib/validation";

export function LoginForm() {
  const t = useTranslations("login");
  const locale = useLocale();
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const [formError, setFormError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);
  const [phoneOn, setPhoneOn] = useState(false);
  const [phone, setPhone] = useState("");

  useEffect(() => {
    let active = true;
    void fetchAuthConfig().then((config) => {
      if (active) {
        setPhoneOn(config.phone_registration_enabled);
      }
    });
    return () => {
      active = false;
    };
  }, []);

  function goNext(next: LoginNext | undefined) {
    if (next === "enroll") {
      router.push(`/${locale}/enroll`);
    } else if (next === "challenge") {
      router.push(`/${locale}/login/challenge`);
    } else {
      router.push(`/${locale}`);
    }
    router.refresh();
  }

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setFormError(null);
    const parsed = loginSchema({
      email: t("emailInvalid"),
      password: t("passwordRequired"),
    }).safeParse({ email, password });
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
      const response = await apiPost(
        "/api/v1/auth/login",
        { email: parsed.data.email, password: parsed.data.password },
        csrf,
      );
      if (response.status === 401) {
        setFormError(t("invalid"));
        return;
      }
      if (response.status === 429) {
        setFormError(t("rateLimited"));
        return;
      }
      if (!response.ok) {
        setFormError(t("genericError"));
        return;
      }
      const body = (await response.json()) as { next?: LoginNext };
      goNext(body.next);
    } catch {
      setFormError(t("genericError"));
    } finally {
      setPending(false);
    }
  }

  async function signInPhone() {
    setFormError(null);
    if (!/^\+[1-9]\d{7,14}$/.test(phone.trim())) {
      setFormError(t("phoneInvalid"));
      return;
    }
    setPending(true);
    try {
      const csrf = await fetchCsrfToken();
      const response = await apiPost(
        "/api/v1/auth/login/phone",
        { phone: phone.trim(), password },
        csrf,
      );
      if (response.status === 401) {
        setFormError(t("invalid"));
        return;
      }
      if (response.status === 429) {
        setFormError(t("rateLimited"));
        return;
      }
      if (!response.ok) {
        setFormError(t("genericError"));
        return;
      }
      const body = (await response.json()) as { next?: LoginNext };
      goNext(body.next);
    } catch {
      setFormError(t("genericError"));
    } finally {
      setPending(false);
    }
  }

  return (
    <form className="flex flex-col gap-md" noValidate onSubmit={(event) => void onSubmit(event)}>
      {formError ? (
        <p role="alert" className="text-sm text-danger">
          {formError}
        </p>
      ) : null}
      <TextField
        id="login-email"
        label={t("email")}
        type="email"
        autoComplete="email"
        value={email}
        error={fieldErrors.email}
        onChange={(event) => setEmail(event.target.value)}
      />
      <TextField
        id="login-password"
        label={t("password")}
        type="password"
        autoComplete="current-password"
        value={password}
        error={fieldErrors.password}
        onChange={(event) => setPassword(event.target.value)}
      />
      <Button type="submit" pending={pending}>
        {pending ? t("submitting") : t("submit")}
      </Button>
      <p className="text-sm text-muted">
        <Link className="font-semibold text-brand underline-offset-2 hover:underline" href={`/${locale}/forgot-password`}>
          {t("forgot")}
        </Link>
      </p>
      <p className="text-sm text-muted">
        {t("needAccount")}{" "}
        <Link className="font-semibold text-brand underline-offset-2 hover:underline" href={`/${locale}/register`}>
          {t("register")}
        </Link>
      </p>
      {phoneOn ? (
        <div className="flex flex-col gap-md border-t border-line pt-md">
          <h2 className="text-lg font-semibold text-ink">{t("phoneTitle")}</h2>
          <TextField
            id="login-phone"
            label={t("phone")}
            type="tel"
            autoComplete="tel"
            value={phone}
            onChange={(event) => setPhone(event.target.value)}
          />
          <Button
            type="button"
            onClick={() => void signInPhone()}
            pending={pending}
          >
            {t("phoneSubmit")}
          </Button>
        </div>
      ) : null}
    </form>
  );
}
