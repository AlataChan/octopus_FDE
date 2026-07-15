import { type ReactNode } from "react";
import { Panel, PanelGroup, PanelResizeHandle } from "react-resizable-panels";
import { useTranslation } from "react-i18next";

type Props = {
  chatCol: ReactNode;
  compileCol: ReactNode;
  header: ReactNode;
  irCol: ReactNode;
  layoutResetVersion: number;
  stepper: ReactNode;
  sidebar: ReactNode;
};

const PANEL_GROUP_AUTOSAVE_ID = "fde-session-panels-v1";
const CONTEXT_PANEL_GROUP_AUTOSAVE_ID = "fde-context-vertical-v2";

export function DesktopWorkbenchLayout({
  chatCol,
  compileCol,
  header,
  irCol,
  layoutResetVersion,
  stepper,
  sidebar
}: Props) {
  const { t } = useTranslation();

  return (
    <div className="lg:flex lg:h-full lg:min-h-0">
      <div className="hidden lg:flex lg:h-full">{sidebar}</div>
      <div className="min-w-0 flex-1 lg:min-h-0">
        <div className="min-h-0 flex-1 lg:h-full">
          <PanelGroup
            autoSaveId={PANEL_GROUP_AUTOSAVE_ID}
            className="h-full w-full"
            direction="horizontal"
            key={layoutResetVersion}
          >
            <Panel className="flex min-h-0 min-w-0 flex-col overflow-hidden" defaultSize={60} id="chat" minSize={36} order={1}>
              {header}
              {stepper}
              <div className="min-h-0 flex-1 p-3">{chatCol}</div>
            </Panel>
            <PanelResizeHandle
              aria-label={t("layout.resizeChatIr")}
              className="group relative w-3 cursor-col-resize rounded-full outline-none focus-visible:ring-2 focus-visible:ring-ring"
            >
              <span className="absolute inset-y-0 left-1/2 w-0.5 -translate-x-1/2 rounded-full bg-border/45 transition-colors group-hover:bg-accent/80 group-data-[resize-handle-state=drag]:bg-accent" />
            </PanelResizeHandle>
            <Panel className="flex min-h-0 min-w-0 flex-col overflow-hidden p-3" defaultSize={40} id="context" minSize={28} order={2}>
              <PanelGroup
                autoSaveId={CONTEXT_PANEL_GROUP_AUTOSAVE_ID}
                className="h-full min-h-0 w-full"
                direction="vertical"
              >
                <Panel className="flex min-h-0 min-w-0 overflow-hidden" defaultSize={30} id="context-ir" minSize={30} order={1}>
                  <div className="h-full min-h-0 w-full overflow-hidden" data-testid="context-ir-pane">{irCol}</div>
                </Panel>
                <PanelResizeHandle
                  aria-label={t("layout.resizeIrCompile")}
                  className="group relative h-3 cursor-row-resize rounded-full outline-none focus-visible:ring-2 focus-visible:ring-ring"
                >
                  <span className="absolute left-0 top-1/2 h-0.5 w-full -translate-y-1/2 rounded-full bg-border/45 transition-colors group-hover:bg-accent/80 group-data-[resize-handle-state=drag]:bg-accent" />
                </PanelResizeHandle>
                <Panel
                  className="flex min-h-0 min-w-0 overflow-hidden"
                  defaultSize={70}
                  id="context-compile"
                  minSize={28}
                  order={2}
                >
                  <div className="h-full min-h-0 w-full overflow-hidden" data-testid="context-compile-pane">{compileCol}</div>
                </Panel>
              </PanelGroup>
            </Panel>
          </PanelGroup>
        </div>
      </div>
    </div>
  );
}
