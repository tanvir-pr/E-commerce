"use client";

import { useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import { useRouter } from "next/navigation";
import { apiPost, fetchCsrfToken, fetchHealth, fetchMe, type Me } from "@/lib/api";
import { Button } from "@/components/Button";

export function HomePanel() {
  const t = useTranslations("home");
  const router = useRouter();
  const [health, setHealth] = useState<"checking" | "ok" | "down">("checking");
  const [me, setMe] = useState<Me | null | undefined>(undefined);
  const [logoutError, setLogoutError] = useState(false);
  const [pending, setPending] = useState(false);

  useEffect(() => {
    let active = true;
    void (async () => {
      const [healthResult, meResult] = await Promise.all([fetchHealth(), fetchMe()]);
      if (!active) {
        return;
      }
      setHealth(healthResult ? "ok" : "down");
      setMe(meResult);
    })();
    return () => {
      active = false;
    };
  }, []);

  async function logout() {
    setPending(true);
    setLogoutError(false);
    try {
      const csrf = await fetchCsrfToken();
      const response = await apiPost("/api/v1/auth/logout", {}, csrf);
      if (!response.ok) {
        setLogoutError(true);
        return;
      }
      setMe(null);
      router.refresh();
    } catch {
      setLogoutError(true);
    } finally {
      setPending(false);
    }
  }

  const healthText =
    health === "checking" ? t("healthChecking") : health === "ok" ? t("healthOk") : t("healthDown");
  const healthClass =
    health === "down"
      ? "text-base font-medium text-danger"
      : health === "ok"
        ? "text-base font-medium text-ok"
        : "text-base font-medium text-muted";

  return (
    <div className="flex flex-col gap-md">
      <p role="status" className={healthClass}>
        {healthText}
      </p>
      {me ? (
        <div className="flex flex-col gap-sm">
          <p className="text-base text-ink">{t("signedInAs", { email: me.email ?? me.phone ?? "" })}</p>
          <p className="text-sm text-muted">{me.email_verified_at ? t("verified") : t("notVerified")}</p>
          {logoutError ? (
            <p role="alert" className="text-sm text-danger">
              {t("logoutError")}
            </p>
          ) : null}
          <Button type="button" onClick={() => void logout()} pending={pending}>
            {pending ? t("loggingOut") : t("logout")}
          </Button>
        </div>
      ) : null}
      {me === null ? <p className="text-base text-muted">{t("guestPrompt")}</p> : null}
    </div>
  );
}
