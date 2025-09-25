"use client";

import { FormEvent, useEffect, useState } from "react";
import { useLocale, useTranslations } from "next-intl";
import Link from "next/link";
import { Button } from "@/components/Button";
import { TextField } from "@/components/TextField";
import { apiPost, fetchAuthConfig, fetchCsrfToken } from "@/lib/api";
import { phoneRegisterSchema, registerSchema } from "@/lib/validation";

const empty = { email: "", password: "", confirmPassword: "" };
const emptyPhone = { name: "", phone: "", password: "", confirmPassword: "" };

export function RegisterForm() {
  const t = useTranslations("register");
  const locale = useLocale();
  const [values, setValues] = useState(empty);
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const [formError, setFormError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);
  const [pending, setPending] = useState(false);
  const [phoneOn, setPhoneOn] = useState(false);
  const [phoneValues, setPhoneValues] = useState(emptyPhone);
  const [phoneCode, setPhoneCode] = useState("");
  const [phoneStep, setPhoneStep] = useState<"form" | "code" | "done">("form");

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

  function update(field: keyof typeof empty, value: string) {
    setValues((current) => ({ ...current, [field]: value }));
    setFieldErrors((current) => {
      if (!current[field]) {
        return current;
      }
      const next = { ...current };
      delete next[field];
      return next;
    });
  }

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSuccess(false);
    setFormError(null);
    const parsed = registerSchema({
      email: t("emailInvalid"),
      password: t("passwordShort"),
      confirm: t("passwordMismatch"),
    }).safeParse(values);
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
        "/api/v1/auth/register",
        { email: parsed.data.email, password: parsed.data.password },
        csrf,
      );
      if (!response.ok) {
        setFormError(t("genericError"));
        return;
      }
      setValues(empty);
      setSuccess(true);
    } catch {
      setFormError(t("genericError"));
    } finally {
      setPending(false);
    }
  }

  async function sendPhoneCode() {
    setFormError(null);
    const parsed = phoneRegisterSchema({
      name: t("nameRequired"),
      phone: t("phoneInvalid"),
      password: t("passwordShort"),
      confirm: t("passwordMismatch"),
    }).safeParse(phoneValues);
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
        "/api/v1/auth/phone/start",
        { name: parsed.data.name, phone: parsed.data.phone, password: parsed.data.password },
        csrf,
      );
      if (!response.ok) {
        setFormError(t("genericError"));
        return;
      }
      setPhoneStep("code");
    } catch {
      setFormError(t("genericError"));
    } finally {
      setPending(false);
    }
  }

  async function confirmPhoneCode() {
    setFormError(null);
    if (!/^\d{6}$/.test(phoneCode.trim())) {
      setFieldErrors({ code: t("codeInvalid") });
      return;
    }
    setPending(true);
    try {
      const csrf = await fetchCsrfToken();
      const response = await apiPost(
        "/api/v1/auth/phone/confirm",
        { phone: phoneValues.phone.trim(), code: phoneCode.trim() },
        csrf,
      );
      if (!response.ok) {
        setFormError(t("phoneError"));
        return;
      }
      setPhoneStep("done");
    } catch {
      setFormError(t("genericError"));
    } finally {
      setPending(false);
    }
  }

  return (
    <div className="flex flex-col gap-lg">
    <form className="flex flex-col gap-md" noValidate onSubmit={(event) => void onSubmit(event)}>
      {success ? (
        <p role="status" className="text-sm font-medium text-ok">
          {t("success")}
        </p>
      ) : null}
      {formError ? (
        <p role="alert" className="text-sm text-danger">
          {formError}
        </p>
      ) : null}
      <TextField
        id="register-email"
        label={t("email")}
        type="email"
        autoComplete="email"
        value={values.email}
        error={fieldErrors.email}
        onChange={(event) => update("email", event.target.value)}
      />
      <TextField
        id="register-password"
        label={t("password")}
        type="password"
        autoComplete="new-password"
        value={values.password}
        error={fieldErrors.password}
        onChange={(event) => update("password", event.target.value)}
      />
      <TextField
        id="register-confirm"
        label={t("confirmPassword")}
        type="password"
        autoComplete="new-password"
        value={values.confirmPassword}
        error={fieldErrors.confirmPassword}
        onChange={(event) => update("confirmPassword", event.target.value)}
      />
      <Button type="submit" pending={pending}>
        {pending ? t("submitting") : t("submit")}
      </Button>
      <p className="text-sm text-muted">
        {t("hasAccount")}{" "}
        <Link className="font-semibold text-brand underline-offset-2 hover:underline" href={`/${locale}/login`}>
          {t("signIn")}
        </Link>
      </p>
    </form>
      {phoneOn ? (
        <div className="flex flex-col gap-md border-t border-line pt-md">
          <h2 className="text-lg font-semibold text-ink">{t("phoneTitle")}</h2>
          <p className="text-sm text-muted">{t("phoneLede")}</p>
          {phoneStep === "done" ? (
            <p role="status" className="text-sm font-medium text-ok">
              {t("phoneVerified")}
            </p>
          ) : null}
          {phoneStep === "form" ? (
            <>
              <TextField
                id="phone-name"
                label={t("name")}
                autoComplete="name"
                value={phoneValues.name}
                error={fieldErrors.name}
                onChange={(event) => setPhoneValues((current) => ({ ...current, name: event.target.value }))}
              />
              <TextField
                id="phone-number"
                label={t("phone")}
                type="tel"
                autoComplete="tel"
                value={phoneValues.phone}
                error={fieldErrors.phone}
                onChange={(event) => setPhoneValues((current) => ({ ...current, phone: event.target.value }))}
              />
              <p className="text-sm text-muted">{t("phoneHint")}</p>
              <TextField
                id="phone-password"
                label={t("password")}
                type="password"
                autoComplete="new-password"
                value={phoneValues.password}
                error={fieldErrors.password}
                onChange={(event) =>
                  setPhoneValues((current) => ({ ...current, password: event.target.value }))
                }
              />
              <TextField
                id="phone-confirm"
                label={t("confirmPassword")}
                type="password"
                autoComplete="new-password"
                value={phoneValues.confirmPassword}
                error={fieldErrors.confirmPassword}
                onChange={(event) =>
                  setPhoneValues((current) => ({ ...current, confirmPassword: event.target.value }))
                }
              />
              <Button type="button" pending={pending} onClick={() => void sendPhoneCode()}>
                {pending ? t("phoneSubmitting") : t("phoneSubmit")}
              </Button>
            </>
          ) : null}
          {phoneStep === "code" ? (
            <>
              <p role="status" className="text-sm font-medium text-ok">
                {t("phoneSuccess")}
              </p>
              <TextField
                id="phone-code"
                label={t("code")}
                inputMode="numeric"
                autoComplete="one-time-code"
                value={phoneCode}
                error={fieldErrors.code}
                onChange={(event) => setPhoneCode(event.target.value)}
              />
              <Button type="button" pending={pending} onClick={() => void confirmPhoneCode()}>
                {pending ? t("codeSubmitting") : t("codeSubmit")}
              </Button>
            </>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}
