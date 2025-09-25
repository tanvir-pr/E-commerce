import { getTranslations } from "next-intl/server";
import Link from "next/link";

export default async function NotFound() {
  const t = await getTranslations("notFound");
  return (
    <main id="main" className="mx-auto w-full max-w-lg px-md py-2xl">
      <h1 className="text-3xl font-semibold text-ink">{t("title")}</h1>
      <Link
        className="mt-md inline-flex min-h-tap items-center font-semibold text-brand underline-offset-2 hover:underline"
        href="/en"
      >
        {t("home")}
      </Link>
    </main>
  );
}
