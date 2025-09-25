import { getLocale, getTranslations } from "next-intl/server";
import Link from "next/link";
import { loadMe } from "@/lib/current-user";

const linkClass =
  "inline-flex min-h-tap items-center rounded-sm px-sm text-sm font-semibold text-brand underline-offset-2 hover:underline";

export async function Header() {
  const t = await getTranslations("nav");
  const locale = await getLocale();
  const me = await loadMe();
  const privileged = me?.roles.includes("staff") || me?.roles.includes("super_admin");
  return (
    <header className="border-b border-line bg-surface">
      <div className="mx-auto flex max-w-3xl flex-wrap items-center justify-between gap-sm px-md py-sm">
        <Link href={`/${locale}`} className="text-lg font-semibold tracking-tight text-ink">
          {t("shopName")}
        </Link>
        <nav aria-label={t("accountLabel")} className="flex items-center gap-2xs">
          {me ? (
            <>
              <Link href={`/${locale}/account`} className={linkClass}>
                {t("account")}
              </Link>
              {privileged ? (
                <Link href={`/${locale}/admin`} className={linkClass}>
                  {t("admin")}
                </Link>
              ) : null}
            </>
          ) : (
            <>
              <Link href={`/${locale}/login`} className={linkClass}>
                {t("signIn")}
              </Link>
              <Link href={`/${locale}/register`} className={linkClass}>
                {t("register")}
              </Link>
            </>
          )}
        </nav>
      </div>
    </header>
  );
}
