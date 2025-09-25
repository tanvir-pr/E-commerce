import { getTranslations, setRequestLocale } from "next-intl/server";
import { ChallengeForm } from "@/components/ChallengeForm";
import { PageShell } from "@/components/PageShell";

export default async function ChallengePage({ params }: { params: Promise<{ locale: string }> }) {
  const { locale } = await params;
  setRequestLocale(locale);
  const t = await getTranslations("challenge");
  return (
    <PageShell title={t("title")} lede={t("lede")}>
      <ChallengeForm />
    </PageShell>
  );
}
