"use client";

import { FormEvent, useEffect, useState } from "react";
import { useLocale, useTranslations } from "next-intl";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Button } from "@/components/Button";
import { TextField } from "@/components/TextField";
import {
  apiGet,
  apiPost,
  apiSend,
  fetchCsrfToken,
  fetchMe,
  type Me,
  type SessionInfo,
} from "@/lib/api";

function when(value: string) {
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return value;
  }
  return parsed.toLocaleString();
}

export function AccountPanel() {
  const t = useTranslations("account");
  const locale = useLocale();
  const router = useRouter();
  const [me, setMe] = useState<Me | null | undefined>(undefined);
  const [name, setName] = useState("");
  const [sessions, setSessions] = useState<SessionInfo[]>([]);
  const [code, setCode] = useState("");
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  useEffect(() => {
    let active = true;
    void (async () => {
      const current = await fetchMe();
      if (!active) {
        return;
      }
      setMe(current);
      setName(current?.name ?? "");
      if (!current) {
        return;
      }
      const response = await apiGet("/api/v1/auth/sessions");
      if (!active || !response.ok) {
        return;
      }
      const body = (await response.json()) as { sessions?: SessionInfo[] };
      setSessions(body.sessions ?? []);
    })();
    return () => {
      active = false;
    };
  }, []);

  if (me === undefined) {
    return <p className="text-base text-muted">{t("loading")}</p>;
  }
  if (me === null) {
    return (
      <p className="text-base text-muted">
        {t("signedOut")}{" "}
        <Link className="font-semibold text-brand underline-offset-2 hover:underline" href={`/${locale}/login`}>
          {t("signIn")}
        </Link>
      </p>
    );
  }

  const privileged = me.roles.includes("staff") || me.roles.includes("super_admin");

  async function saveName(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setMessage(null);
    setError(null);
    if (!name.trim()) {
      setError(t("nameRequired"));
      return;
    }
    setPending(true);
    try {
      const csrf = await fetchCsrfToken();
      const response = await apiSend("PATCH", "/api/v1/users/me", { name: name.trim() }, csrf);
      if (!response.ok) {
        setError(t("genericError"));
        return;
      }
      setMe((await response.json()) as Me);
      setMessage(t("saved"));
    } catch {
      setError(t("genericError"));
    } finally {
      setPending(false);
    }
  }

  async function logoutEverywhere() {
    setError(null);
    setPending(true);
    try {
      const csrf = await fetchCsrfToken();
      const response = await apiPost("/api/v1/auth/logout-everywhere", {}, csrf);
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

  async function disableTotp(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setMessage(null);
    if (code.trim().length < 6) {
      setError(t("codeInvalid"));
      return;
    }
    setPending(true);
    try {
      const csrf = await fetchCsrfToken();
      const response = await apiPost("/api/v1/auth/totp/disable", { code: code.trim() }, csrf);
      if (response.status === 401) {
        setError(t("disableInvalid"));
        return;
      }
      if (!response.ok) {
        setError(t("genericError"));
        return;
      }
      setCode("");
      setMessage(t("disabled"));
      const current = await fetchMe();
      setMe(current);
    } catch {
      setError(t("genericError"));
    } finally {
      setPending(false);
    }
  }

  return (
    <div className="flex flex-col gap-lg">
      {message ? (
        <p role="status" className="text-sm font-medium text-ok">
          {message}
        </p>
      ) : null}
      {error ? (
        <p role="alert" className="text-sm text-danger">
          {error}
        </p>
      ) : null}
      <dl className="flex flex-col gap-sm text-sm">
        <div>
          <dt className="font-medium text-ink">{t("email")}</dt>
          <dd className="text-muted">{me.email ?? t("none")}</dd>
          <dd className="text-muted">{me.email_verified_at ? t("emailVerified") : t("emailUnverified")}</dd>
        </div>
        <div>
          <dt className="font-medium text-ink">{t("phone")}</dt>
          <dd className="text-muted">{me.phone ?? t("none")}</dd>
          <dd className="text-muted">{me.phone_verified_at ? t("phoneVerified") : t("phoneUnverified")}</dd>
        </div>
      </dl>
      <form className="flex flex-col gap-md" onSubmit={(event) => void saveName(event)}>
        <TextField id="account-name" label={t("name")} value={name} onChange={(event) => setName(event.target.value)} />
        <Button type="submit" pending={pending}>
          {pending ? t("saving") : t("save")}
        </Button>
      </form>
      <button
        type="button"
        className="text-left text-sm font-semibold text-brand underline-offset-2 hover:underline"
        onClick={() => {
          window.location.assign("/api/v1/users/me/export");
        }}
      >
        {t("export")}
      </button>
      <section className="flex flex-col gap-sm">
        <h2 className="text-lg font-semibold text-ink">{t("sessionsTitle")}</h2>
        {sessions.length === 0 ? <p className="text-sm text-muted">{t("sessionsEmpty")}</p> : null}
        <ul className="flex flex-col gap-sm">
          {sessions.map((session) => (
            <li key={session.family_id} className="rounded-md border border-line px-sm py-sm text-sm">
              <p className="font-medium text-ink">{session.current ? t("sessionCurrent") : t("sessionOther")}</p>
              <p className="text-muted">{t("sessionCreated", { time: when(session.created_at) })}</p>
              <p className="text-muted">{t("sessionExpires", { time: when(session.expires_at) })}</p>
            </li>
          ))}
        </ul>
        <Button type="button" pending={pending} onClick={() => void logoutEverywhere()}>
          {pending ? t("loggingOut") : t("logoutEverywhere")}
        </Button>
      </section>
      <section className="flex flex-col gap-sm">
        <h2 className="text-lg font-semibold text-ink">{t("totpTitle")}</h2>
        <p className="text-sm text-muted">{me.totp_enabled ? t("totpOn") : t("totpOff")}</p>
        {privileged ? <p className="text-sm text-muted">{t("totpRequired")}</p> : null}
        {!me.totp_enabled ? (
          <Link className="font-semibold text-brand underline-offset-2 hover:underline" href={`/${locale}/enroll`}>
            {t("enroll")}
          </Link>
        ) : null}
        {me.totp_enabled && !privileged ? (
          <form className="flex flex-col gap-md" onSubmit={(event) => void disableTotp(event)}>
            <TextField
              id="disable-code"
              label={t("disableCode")}
              autoComplete="one-time-code"
              value={code}
              onChange={(event) => setCode(event.target.value)}
            />
            <Button type="submit" pending={pending}>
              {pending ? t("disabling") : t("disableSubmit")}
            </Button>
          </form>
        ) : null}
      </section>
    </div>
  );
}
