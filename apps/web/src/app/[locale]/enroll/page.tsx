import { getTranslations, setRequestLocale } from "next-intl/server";
import { EnrollForm } from "@/components/EnrollForm";
import { PageShell } from "@/components/PageShell";

export default async function EnrollPage({ params }: { params: Promise<{ locale: string }> }) {
  const { locale } = await params;
  setRequestLocale(locale);
  const t = await getTranslations("enroll");
  return (
    <PageShell title={t("title")} lede={t("lede")}>
      <EnrollForm />
    </PageShell>
  );
}
