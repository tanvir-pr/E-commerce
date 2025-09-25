import { getTranslations, setRequestLocale } from "next-intl/server";
import { LoginForm } from "@/components/LoginForm";
import { PageShell } from "@/components/PageShell";

export default async function LoginPage({ params }: { params: Promise<{ locale: string }> }) {
  const { locale } = await params;
  setRequestLocale(locale);
  const t = await getTranslations("login");
  return (
    <PageShell title={t("title")} lede={t("lede")}>
      <LoginForm />
    </PageShell>
  );
}
