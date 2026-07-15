import { type ReactNode } from "react";
import { useTranslation } from "react-i18next";
import { Menu } from "lucide-react";
import { Button } from "../ui/Button";

type Props = {
  chatCol: ReactNode;
  compileCol: ReactNode;
  header: ReactNode;
  irCol: ReactNode;
  mobileSidebar: ReactNode;
  mobileSidebarOpen: boolean;
  sidebarLabel: string;
  stepper: ReactNode;
  onCloseSidebar: () => void;
  onOpenSidebar: () => void;
};

export function MobileWorkbenchLayout({
  chatCol,
  compileCol,
  header,
  irCol,
  mobileSidebar,
  mobileSidebarOpen,
  sidebarLabel,
  stepper,
  onCloseSidebar,
  onOpenSidebar
}: Props) {
  const { t } = useTranslation();

  return (
    <>
      <div className="flex h-12 items-center justify-between border-b border-border/30 bg-bg-surface/85 px-3 lg:hidden">
        <Button
          aria-label={t("sidebar.openMobile")}
          icon={<Menu aria-hidden className="h-4 w-4" />}
          size="sm"
          variant="ghost"
          onClick={onOpenSidebar}
        >
          {sidebarLabel}
        </Button>
      </div>
      {mobileSidebarOpen ? (
        <div className="fixed inset-0 z-40 flex lg:hidden">
          <button
            aria-label={t("sidebar.closeMobile")}
            className="absolute inset-0 bg-primary/40"
            type="button"
            onClick={onCloseSidebar}
          />
          <div className="relative z-10 h-full">
            {mobileSidebar}
          </div>
        </div>
      ) : null}
      <div className="grid gap-4 p-4 md:grid-cols-8 lg:h-full lg:min-h-0 lg:overflow-y-auto">
        <div className="md:col-span-8">
          {header}
          {stepper}
        </div>
        <div className="md:col-span-8">{chatCol}</div>
        <div className="max-h-[70vh] overflow-auto md:col-span-5">{irCol}</div>
        <div className="md:col-span-3">{compileCol}</div>
      </div>
    </>
  );
}
