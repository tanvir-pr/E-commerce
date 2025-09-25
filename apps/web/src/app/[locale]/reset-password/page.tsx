import { Suspense } from "react";
import { getTranslations, setRequestLocale } from "next-intl/server";
import { PageShell } from "@/components/PageShell";
import { TokenPasswordForm } from "@/components/TokenPasswordForm";

export default async function ResetPasswordPage({ params }: { params: Promise<{ locale: string }> }) {
  const { locale } = await params;
  setRequestLocale(locale);
  const t = await getTranslations("reset");
  return (
    <PageShell title={t("title")} lede={t("lede")}>
      <Suspense fallback={<p className="text-base text-muted">{t("missing")}</p>}>
        <TokenPasswordForm namespace="reset" path="/api/v1/auth/reset-password" />
      </Suspense>
    </PageShell>
  );
}
