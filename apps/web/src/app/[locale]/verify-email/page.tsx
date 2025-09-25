import { Suspense } from "react";
import { getTranslations, setRequestLocale } from "next-intl/server";
import { PageShell } from "@/components/PageShell";
import { VerifyEmail } from "@/components/VerifyEmail";

export default async function VerifyEmailPage({ params }: { params: Promise<{ locale: string }> }) {
  const { locale } = await params;
  setRequestLocale(locale);
  const t = await getTranslations("verify");
  return (
    <PageShell title={t("title")}>
      <Suspense fallback={<p className="text-base text-muted">{t("checking")}</p>}>
        <VerifyEmail />
      </Suspense>
    </PageShell>
  );
}
