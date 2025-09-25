import { getTranslations, setRequestLocale } from "next-intl/server";
import { ForgotPasswordForm } from "@/components/ForgotPasswordForm";
import { PageShell } from "@/components/PageShell";

export default async function ForgotPasswordPage({ params }: { params: Promise<{ locale: string }> }) {
  const { locale } = await params;
  setRequestLocale(locale);
  const t = await getTranslations("forgot");
  return (
    <PageShell title={t("title")} lede={t("lede")}>
      <ForgotPasswordForm />
    </PageShell>
  );
}
