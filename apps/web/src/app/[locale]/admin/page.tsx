import { getTranslations, setRequestLocale } from "next-intl/server";
import Link from "next/link";
import { AdminPanel } from "@/components/AdminPanel";
import { PageShell } from "@/components/PageShell";
import { loadMe } from "@/lib/current-user";

export default async function AdminPage({ params }: { params: Promise<{ locale: string }> }) {
  const { locale } = await params;
  setRequestLocale(locale);
  const t = await getTranslations("admin");
  const me = await loadMe();
  const privileged = Boolean(me && (me.roles.includes("staff") || me.roles.includes("super_admin")));

  let body;
  if (!me) {
    body = (
      <p className="text-base text-muted">
        {t("signedOut")}{" "}
        <Link className="font-semibold text-brand underline-offset-2 hover:underline" href={`/${locale}/login`}>
          {t("signIn")}
        </Link>
      </p>
    );
  } else if (!privileged) {
    body = (
      <p role="alert" className="text-base text-danger">
        {t("forbidden")}
      </p>
    );
  } else if (!me.totp_enabled) {
    body = (
      <div className="flex flex-col gap-sm">
        <p className="text-base text-ink">{t("enrollRequired")}</p>
        <Link className="font-semibold text-brand underline-offset-2 hover:underline" href={`/${locale}/enroll`}>
          {t("enroll")}
        </Link>
      </div>
    );
  } else {
    body = <AdminPanel email={me.email ?? me.phone ?? ""} superAdmin={me.roles.includes("super_admin")} />;
  }

  return (
    <PageShell title={t("title")} lede={t("lede")} wide>
      {body}
    </PageShell>
  );
}
