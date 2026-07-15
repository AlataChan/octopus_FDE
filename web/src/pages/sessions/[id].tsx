import { useParams } from "react-router-dom";
import { ChatColumn } from "../../components/console/ChatColumn";
import { CompileColumn } from "../../components/console/CompileColumn";
import { DesktopWorkbenchLayout } from "../../components/console/DesktopWorkbenchLayout";
import { IRColumn } from "../../components/console/IRColumn";
import { LLMConfigModal } from "../../components/console/LLMConfigModal";
import { MobileWorkbenchLayout } from "../../components/console/MobileWorkbenchLayout";
import { SessionsSidebar } from "../../components/console/SessionsSidebar";
import { StateStepper } from "../../components/console/StateStepper";
import { TemplateModal } from "../../components/console/TemplateModal";
import { WorkbenchHeader } from "../../components/console/WorkbenchHeader";
import { useSessionWorkbench } from "../../hooks/useSessionWorkbench";

export default function SessionDetailPage() {
  const params = useParams();
  const sessionId = params.id || "";
  const wb = useSessionWorkbench(sessionId);

  const chatCol = (
    <ChatColumn
      isSending={wb.plannerTurn.isPending}
      turns={wb.turns.data || []}
      onSend={(message) => wb.plannerTurn.mutate(message)}
    />
  );
  const irCol = (
    <IRColumn
      compileWarningCount={wb.compileWarningCount}
      compileWarnings={wb.compileWarnings}
      diff={wb.diff.data || null}
      diffSummary={wb.flowDiffSummary}
      errors={wb.errors}
      highlightedPath={wb.highlightedPath}
      ir={wb.ir.data?.ir || null}
      resetKey={sessionId}
      selectedNodeId={wb.selectedNodeId}
      status={wb.ir.data?.validator_status || wb.t("session.noIr")}
      onSelectedNodeIdChange={wb.setSelectedNodeId}
      onSelectPath={wb.setHighlightedPath}
    />
  );
  const compileCol = (
    <CompileColumn
      artifacts={wb.session.data?.artifacts || []}
      bindings={wb.bindings.data || []}
      isCompiling={wb.compile.isPending}
      onCompile={wb.runCompile}
      onDownload={(artifact) => void wb.download(artifact)}
    />
  );
  const header = (
    <WorkbenchHeader
      session={wb.session.data || null}
      onRename={(title) => wb.rename.mutateAsync(title)}
      onResetLayout={wb.resetLayout}
    />
  );
  const stepper = (
    <div className="shrink-0 border-b border-border/30 bg-bg-surface/75 px-3 py-2">
      <StateStepper state={wb.session.data?.state || "init"} />
    </div>
  );
  const desktopSidebar = (
    <SessionsSidebar
      currentSessionId={sessionId}
      defaultCollapsed={!wb.isXl}
      onCreateSession={wb.openTemplateModal}
    />
  );
  const mobileSidebar = (
    <SessionsSidebar
      currentSessionId={sessionId}
      forceExpanded
      onCreateSession={wb.openTemplateModal}
    />
  );

  const layout = wb.isLg ? (
    <DesktopWorkbenchLayout
      chatCol={chatCol}
      compileCol={compileCol}
      header={header}
      irCol={irCol}
      layoutResetVersion={wb.layoutResetVersion}
      stepper={stepper}
      sidebar={desktopSidebar}
    />
  ) : (
    <MobileWorkbenchLayout
      chatCol={chatCol}
      compileCol={compileCol}
      header={header}
      irCol={irCol}
      mobileSidebar={mobileSidebar}
      mobileSidebarOpen={wb.mobileSidebarOpen}
      sidebarLabel={wb.t("workbench.sessionsLink")}
      stepper={stepper}
      onCloseSidebar={() => wb.setMobileSidebarOpen(false)}
      onOpenSidebar={() => wb.setMobileSidebarOpen(true)}
    />
  );

  return (
    <section className="min-h-[calc(100vh-56px)] lg:h-[calc(100dvh-56px)] lg:overflow-hidden">
      {layout}
      <LLMConfigModal
        isSaving={wb.setConfig.isPending}
        open={wb.needsConfig && !wb.configDismissed}
        onOpenChange={(open) => {
          if (!open) {
            wb.setConfigDismissed(true);
          }
        }}
        onSubmit={wb.saveConfig}
      />
      <TemplateModal
        creatingBlank={wb.create.isPending}
        creatingTemplateId={(wb.createFromTemplate.variables as string | undefined) || null}
        open={wb.templateModalOpen}
        onCreateBlank={() => wb.create.mutate()}
        onCreateTemplate={(templateId) => wb.createFromTemplate.mutate(templateId)}
        onOpenChange={wb.setTemplateModalOpen}
      />
    </section>
  );
}
