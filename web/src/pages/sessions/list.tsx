import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { FileCode2, MoreVertical, Plus, Trash2 } from "lucide-react";
import { useTranslation } from "react-i18next";
import { Link, useNavigate } from "react-router-dom";
import { DeleteSessionDialog } from "../../components/console/DeleteSessionDialog";
import { TemplateModal } from "../../components/console/TemplateModal";
import { Button } from "../../components/ui/Button";
import { Card, CardBody } from "../../components/ui/Card";
import { Chip, type ChipVariant } from "../../components/ui/Chip";
import { createSession, createSessionFromTemplate, deleteSession, listSessions } from "../../lib/api";
import type { SessionSummary } from "../../lib/types";

export default function SessionListPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [templateModalOpen, setTemplateModalOpen] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState<SessionSummary | null>(null);
  const [deleteError, setDeleteError] = useState(false);
  const sessions = useQuery({
    queryKey: ["sessions"],
    queryFn: listSessions
  });
  const create = useMutation({
    mutationFn: createSession,
    onSuccess: async (row) => {
      await queryClient.invalidateQueries({ queryKey: ["sessions"] });
      navigate(`/sessions/${row.session_id}`);
    }
  });
  const createFromTemplate = useMutation({
    mutationFn: (templateId: string) => createSessionFromTemplate(templateId),
    onSuccess: async (row) => {
      await queryClient.invalidateQueries({ queryKey: ["sessions"] });
      setTemplateModalOpen(false);
      navigate(`/sessions/${row.session_id}`);
    }
  });
  const remove = useMutation({
    mutationFn: (sessionId: string) => deleteSession(sessionId),
    onMutate: () => {
      setDeleteError(false);
    },
    onSuccess: async () => {
      setDeleteTarget(null);
      setDeleteError(false);
      await queryClient.invalidateQueries({ queryKey: ["sessions"] });
    },
    onError: () => {
      setDeleteError(true);
    }
  });
  const isCreating = create.isPending || createFromTemplate.isPending;

  return (
    <section className="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.18em] text-accent/80">
            {t("sessions.kicker")}
          </p>
          <h1 className="mt-2 text-3xl font-semibold tracking-tight text-fg">{t("sessions.title")}</h1>
          <p className="mt-2 max-w-2xl text-sm leading-6 text-fg-muted">{t("sessions.subtitle")}</p>
        </div>
        <Button
          icon={<Plus aria-hidden className="h-4 w-4" />}
          loading={isCreating}
          variant="primary"
          disabled={isCreating}
          onClick={() => setTemplateModalOpen(true)}
        >
          {isCreating ? t("sessions.creating") : t("sessions.create")}
        </Button>
      </div>
      <div className="mt-7">
        {sessions.isPending ? (
          <Card>
            <CardBody className="text-sm text-fg-muted">{t("sessions.loading")}</CardBody>
          </Card>
        ) : sessions.isError ? (
          <Card>
            <CardBody className="text-sm text-destructive">{t("sessions.error")}</CardBody>
          </Card>
        ) : sessions.data.length === 0 ? (
          <Card>
            <CardBody className="text-sm text-fg-muted">{t("sessions.empty")}</CardBody>
          </Card>
        ) : (
          <div className="grid gap-4 sm:grid-cols-1 md:grid-cols-2 lg:grid-cols-3">
            {sessions.data.map((session) => (
              <SessionCard
                key={session.session_id}
                session={session}
                onDeleteRequest={(target) => {
                  setDeleteError(false);
                  setDeleteTarget(target);
                }}
              />
            ))}
          </div>
        )}
      </div>
      <TemplateModal
        creatingBlank={create.isPending}
        creatingTemplateId={(createFromTemplate.variables as string | undefined) || null}
        open={templateModalOpen}
        onCreateBlank={() => create.mutate()}
        onCreateTemplate={(templateId) => createFromTemplate.mutate(templateId)}
        onOpenChange={setTemplateModalOpen}
      />
      <DeleteSessionDialog
        deleting={remove.isPending}
        error={deleteError ? t("sessions.delete.error") : null}
        open={Boolean(deleteTarget)}
        sessionTitle={deleteTarget ? sessionTitle(deleteTarget) : null}
        onConfirm={() => {
          if (deleteTarget) {
            remove.mutate(deleteTarget.session_id);
          }
        }}
        onOpenChange={(open) => {
          if (!open) {
            setDeleteTarget(null);
            setDeleteError(false);
          }
        }}
      />
    </section>
  );
}

function SessionCard({
  session,
  onDeleteRequest
}: {
  session: SessionSummary;
  onDeleteRequest: (session: SessionSummary) => void;
}) {
  const { i18n, t } = useTranslation();
  const [menuOpen, setMenuOpen] = useState(false);
  const hasIr = Boolean(session.latest_ir_sha256);
  const title = sessionTitle(session);
  return (
    <div className="group relative rounded-lg outline-none">
      <Link className="block h-full rounded-lg outline-none" to={`/sessions/${session.session_id}`}>
        <Card className="h-full transition-transform duration-150 hover:-translate-y-0.5 hover:ring-accent/30">
        <CardBody className="flex h-full flex-col gap-5">
          <div className="flex items-start gap-3 pr-9">
            <div className="min-w-0">
              <div className="flex items-center gap-2">
                <FileCode2 aria-hidden className="h-4 w-4 text-accent" />
                <h2 className="truncate font-mono text-sm font-semibold text-fg">
                  {title}
                </h2>
              </div>
              <p className="mt-2 line-clamp-2 text-sm leading-6 text-fg-muted">
                {hasIr ? t("sessions.card.hasIr") : t("sessions.card.noTurns")}
              </p>
            </div>
          </div>
          <div className="mt-auto flex flex-wrap items-center gap-2">
            <Chip variant={chipForState(session.state)}>{session.state}</Chip>
            <span className="rounded-full bg-bg-app/70 px-2.5 py-1 text-xs font-medium text-fg-muted ring-1 ring-border/40">
              {session.state === "compiled"
                ? t("sessions.card.artifactsPlus")
                : t("sessions.card.artifacts", { count: 0 })}
            </span>
          </div>
          <div className="flex items-center justify-between border-t border-border/30 pt-3 text-xs text-fg-muted">
            <span className="font-mono">{session.latest_ir_sha256?.slice(0, 12) || t("sessions.noIr")}</span>
            <span>{relativeTime(session.updated_at, i18n.language)}</span>
          </div>
        </CardBody>
      </Card>
      </Link>
      <button
        aria-expanded={menuOpen}
        aria-label={t("sessions.card.menu")}
        className="absolute right-4 top-4 rounded-md p-1 text-fg-muted opacity-80 hover:bg-bg-muted hover:text-fg"
        type="button"
        onClick={(event) => {
          event.preventDefault();
          event.stopPropagation();
          setMenuOpen((open) => !open);
        }}
      >
        <MoreVertical aria-hidden className="h-4 w-4" />
      </button>
      {menuOpen ? (
        <div
          className="absolute right-4 top-11 z-20 min-w-36 rounded-lg border border-border/50 bg-bg-surface p-1 shadow-glow"
          role="menu"
        >
          <button
            className="flex w-full items-center gap-2 rounded-md px-3 py-2 text-left text-sm text-destructive hover:bg-destructive/10"
            role="menuitem"
            type="button"
            onClick={() => {
              setMenuOpen(false);
              onDeleteRequest(session);
            }}
          >
            <Trash2 aria-hidden className="h-4 w-4" />
            {t("sessions.delete.menu")}
          </button>
        </div>
      ) : null}
    </div>
  );
}

function sessionTitle(session: SessionSummary): string {
  return session.display_title || `Session ${session.session_id.slice(0, 8)}`;
}

function chipForState(state: string): ChipVariant {
  if (state === "compiled") {
    return "compiled";
  }
  if (state === "validated") {
    return "validated";
  }
  if (state === "llm_config_set") {
    return "llm_config_set";
  }
  return "draft";
}

function relativeTime(value: string, language: string): string {
  const deltaMs = Date.now() - new Date(value).getTime();
  const minutes = Math.max(0, Math.round(deltaMs / 60000));
  const formatter = new Intl.RelativeTimeFormat(language.startsWith("zh") ? "zh" : "en", {
    numeric: "auto"
  });
  if (minutes < 1) {
    return formatter.format(0, "minute");
  }
  if (minutes < 60) {
    return formatter.format(-minutes, "minute");
  }
  const hours = Math.round(minutes / 60);
  if (hours < 24) {
    return formatter.format(-hours, "hour");
  }
  return formatter.format(-Math.round(hours / 24), "day");
}
