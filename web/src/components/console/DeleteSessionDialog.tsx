import { AlertTriangle } from "lucide-react";
import { useTranslation } from "react-i18next";
import { Button } from "../ui/Button";
import { CardBody, CardHeader } from "../ui/Card";
import { Modal } from "../ui/Modal";

type DeleteSessionDialogProps = {
  deleting?: boolean;
  error?: string | null;
  onConfirm: () => void;
  onOpenChange: (open: boolean) => void;
  open: boolean;
  sessionTitle?: string | null;
};

export function DeleteSessionDialog({
  deleting = false,
  error,
  onConfirm,
  onOpenChange,
  open,
  sessionTitle
}: DeleteSessionDialogProps) {
  const { t } = useTranslation();
  const title = sessionTitle || t("sessions.delete.fallbackTitle");

  return (
    <Modal
      labelledBy="delete-session-title"
      open={open}
      onOpenChange={(nextOpen) => {
        if (!deleting) {
          onOpenChange(nextOpen);
        }
      }}
    >
      <CardHeader
        title={<span id="delete-session-title">{t("sessions.delete.title")}</span>}
        subtitle={t("sessions.delete.subtitle")}
      />
      <CardBody className="grid gap-5">
        <div className="flex gap-3 rounded-lg border border-destructive/25 bg-destructive/10 p-3 text-sm leading-6 text-fg">
          <AlertTriangle aria-hidden className="mt-0.5 h-5 w-5 shrink-0 text-destructive" />
          <p>{t("sessions.delete.description", { title })}</p>
        </div>
        {error ? (
          <p className="text-sm text-destructive" role="alert">
            {error}
          </p>
        ) : null}
        <div className="flex justify-end gap-2">
          <Button disabled={deleting} variant="secondary" onClick={() => onOpenChange(false)}>
            {t("common.cancel")}
          </Button>
          <Button
            className="bg-destructive text-white hover:bg-destructive/90"
            loading={deleting}
            variant="primary"
            onClick={onConfirm}
          >
            {deleting ? t("sessions.delete.deleting") : t("sessions.delete.confirm")}
          </Button>
        </div>
      </CardBody>
    </Modal>
  );
}
