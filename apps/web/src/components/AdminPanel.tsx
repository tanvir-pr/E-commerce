"use client";

import { FormEvent, useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import { Button } from "@/components/Button";
import { TextField } from "@/components/TextField";
import { apiGet, apiPost, fetchCsrfToken, type AuditEvent } from "@/lib/api";

const permissions = ["support", "warehouse", "moderation"] as const;

function ShieldIcon() {
  return (
    <svg aria-hidden="true" viewBox="0 0 24 24" className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M12 3 5 6v6c0 4.5 3 6.5 7 8 4-1.5 7-3.5 7-8V6l-7-3z" />
    </svg>
  );
}

export function AdminPanel({ email, superAdmin }: { email: string; superAdmin: boolean }) {
  const t = useTranslations("admin");
  const [events, setEvents] = useState<AuditEvent[] | null>(null);
  const [staffEmail, setStaffEmail] = useState("");
  const [name, setName] = useState("");
  const [selected, setSelected] = useState<string[]>([]);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  useEffect(() => {
    if (!superAdmin) {
      return;
    }
    let active = true;
    void (async () => {
      const response = await apiGet("/api/v1/admin/audit?limit=50");
      if (!active || !response.ok) {
        return;
      }
      const body = (await response.json()) as { events?: AuditEvent[] };
      setEvents(body.events ?? []);
    })();
    return () => {
      active = false;
    };
  }, [superAdmin]);

  function toggle(permission: string) {
    setSelected((current) =>
      current.includes(permission) ? current.filter((item) => item !== permission) : [...current, permission],
    );
  }

  async function createStaff(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setMessage(null);
    setError(null);
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(staffEmail.trim())) {
      setError(t("emailInvalid"));
      return;
    }
    if (!name.trim()) {
      setError(t("nameRequired"));
      return;
    }
    setPending(true);
    try {
      const csrf = await fetchCsrfToken();
      const response = await apiPost(
        "/api/v1/admin/staff",
        { email: staffEmail.trim(), name: name.trim(), permissions: selected },
        csrf,
      );
      if (response.status === 409) {
        setError(t("conflict"));
        return;
      }
      if (!response.ok) {
        setError(t("genericError"));
        return;
      }
      setStaffEmail("");
      setName("");
      setSelected([]);
      setMessage(t("created"));
      const audit = await apiGet("/api/v1/admin/audit?limit=50");
      if (audit.ok) {
        const body = (await audit.json()) as { events?: AuditEvent[] };
        setEvents(body.events ?? []);
      }
    } catch {
      setError(t("genericError"));
    } finally {
      setPending(false);
    }
  }

  const labels: Record<(typeof permissions)[number], string> = {
    support: t("permissionSupport"),
    warehouse: t("permissionWarehouse"),
    moderation: t("permissionModeration"),
  };

  return (
    <div className="flex flex-col gap-lg">
      <p className="inline-flex items-center gap-sm text-sm text-muted">
        <ShieldIcon />
        {t("navPlaceholder")}
      </p>
      <p className="text-base text-ink">{t("signedIn", { email })}</p>
      {superAdmin ? (
        <form className="flex flex-col gap-md" onSubmit={(event) => void createStaff(event)}>
          <h2 className="text-lg font-semibold text-ink">{t("createTitle")}</h2>
          <p className="text-sm text-muted">{t("createLede")}</p>
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
          <TextField
            id="staff-email"
            label={t("email")}
            type="email"
            autoComplete="off"
            value={staffEmail}
            onChange={(event) => setStaffEmail(event.target.value)}
          />
          <TextField
            id="staff-name"
            label={t("name")}
            value={name}
            onChange={(event) => setName(event.target.value)}
          />
          <fieldset className="flex flex-col gap-xs">
            <legend className="sr-only">{t("createTitle")}</legend>
            {permissions.map((permission) => (
              <label key={permission} className="flex min-h-tap items-center gap-sm text-sm text-ink">
                <input
                  type="checkbox"
                  checked={selected.includes(permission)}
                  onChange={() => toggle(permission)}
                />
                {labels[permission]}
              </label>
            ))}
          </fieldset>
          <Button type="submit" pending={pending}>
            {pending ? t("creating") : t("create")}
          </Button>
        </form>
      ) : null}
      {superAdmin ? (
        <section className="flex flex-col gap-sm">
          <h2 className="text-lg font-semibold text-ink">{t("auditTitle")}</h2>
          {events === null ? <p className="text-sm text-muted">{t("loading")}</p> : null}
          {events?.length === 0 ? <p className="text-sm text-muted">{t("auditEmpty")}</p> : null}
          {events && events.length > 0 ? (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm">
                <thead>
                  <tr className="border-b border-line text-muted">
                    <th className="py-xs pr-sm font-medium">{t("auditActor")}</th>
                    <th className="py-xs pr-sm font-medium">{t("auditAction")}</th>
                    <th className="py-xs pr-sm font-medium">{t("auditEntity")}</th>
                    <th className="py-xs font-medium">{t("auditTime")}</th>
                  </tr>
                </thead>
                <tbody>
                  {events.map((event) => (
                    <tr key={event.id} className="border-b border-line">
                      <td className="py-xs pr-sm">{event.actor_email ?? t("unknownActor")}</td>
                      <td className="py-xs pr-sm">{event.action}</td>
                      <td className="py-xs pr-sm">{event.entity_type}</td>
                      <td className="py-xs">{new Date(event.created_at).toLocaleString()}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : null}
        </section>
      ) : null}
    </div>
  );
}
