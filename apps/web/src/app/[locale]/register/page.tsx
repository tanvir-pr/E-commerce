import { getTranslations, setRequestLocale } from "next-intl/server";
import { PageShell } from "@/components/PageShell";
import { RegisterForm } from "@/components/RegisterForm";

export default async function RegisterPage({ params }: { params: Promise<{ locale: string }> }) {
  const { locale } = await params;
  setRequestLocale(locale);
  const t = await getTranslations("register");
  return (
    <PageShell title={t("title")} lede={t("lede")}>
      <RegisterForm />
    </PageShell>
  );
}
