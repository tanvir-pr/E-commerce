import { getTranslations, setRequestLocale } from "next-intl/server";
import Link from "next/link";
import { AccountPanel } from "@/components/AccountPanel";
import { PageShell } from "@/components/PageShell";
import { loadMe } from "@/lib/current-user";

export default async function AccountPage({ params }: { params: Promise<{ locale: string }> }) {
  const { locale } = await params;
  setRequestLocale(locale);
  const t = await getTranslations("account");
  const me = await loadMe();
  return (
    <PageShell title={t("title")} lede={t("lede")} wide>
      {me ? (
        <AccountPanel />
      ) : (
        <p className="text-base text-muted">
          {t("signedOut")}{" "}
          <Link className="font-semibold text-brand underline-offset-2 hover:underline" href={`/${locale}/login`}>
            {t("signIn")}
          </Link>
        </p>
      )}
    </PageShell>
  );
}
