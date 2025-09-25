import { getTranslations, setRequestLocale } from "next-intl/server";
import { HomePanel } from "@/components/HomePanel";
import { PageShell } from "@/components/PageShell";

export default async function HomePage({ params }: { params: Promise<{ locale: string }> }) {
  const { locale } = await params;
  setRequestLocale(locale);
  const t = await getTranslations("home");
  return (
    <PageShell title={t("title")} lede={t("tagline")}>
      <HomePanel />
    </PageShell>
  );
}
