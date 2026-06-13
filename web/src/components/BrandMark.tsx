import { useTranslation } from "react-i18next";
import { cn } from "../lib/cn";

export const BRAND_LOGO_SRC = "/brand/octopus-praser-icon-1024.png";

type BrandMarkProps = {
  className?: string;
  iconClassName?: string;
  showWordmark?: boolean;
  textClassName?: string;
};

export function BrandMark({
  className,
  iconClassName,
  showWordmark = true,
  textClassName
}: BrandMarkProps) {
  const { t } = useTranslation();

  return (
    <span className={cn("inline-flex min-w-0 items-center gap-2", className)}>
      <img
        alt="Octopus FDE logo"
        className={cn(
          "shrink-0 object-cover shadow-[0_0_24px_rgb(var(--accent)/0.28)] ring-1 ring-accent/30",
          iconClassName ? null : "h-9 w-9 rounded-lg",
          iconClassName
        )}
        src={BRAND_LOGO_SRC}
      />
      {showWordmark ? (
        <span className={cn("truncate text-sm font-semibold text-fg", textClassName)}>
          {t("app.title")}
        </span>
      ) : null}
    </span>
  );
}
