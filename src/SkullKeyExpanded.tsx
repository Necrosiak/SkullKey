import { ModalRoot, Navigation, ServerAPI, showModal } from "decky-frontend-lib";
import { useEffect, useState } from "react";
import { FaSkull as Skull, FaDownload as Download, FaCog as Cog } from "react-icons/fa";
import { deferredView } from "./deferredView";
import { ExpandedFrame, ExpandedSection } from "./ExpandedFrame";
import { aboutPages } from "./About";
import { Content } from "./ContentTabs";
import { SkullKeyDownloads } from "./Components/DownloadsSection";
import { Loading } from "./Components/Loading";
import { ActionCard, storeTheme } from "./Components/Styled";
import { executeAction } from "./Utils/executeAction";
import { ActionSet, ExecuteArgs, StoreTabsContent } from "./Types/Types";
import { t, tabLabel } from "./i18n";

const Modal = ModalRoot as any;
const FaSkull = Skull as any, FaDownload = Download as any, FaCog = Cog as any;
let modal: { Close: () => void } | null = null;
let opening = false;
let lastSection = "downloads";
let routeServerAPI: ServerAPI | null = null;
const deferredExpanded = deferredView(() => { if (routeServerAPI) openSkullKeyExpanded(routeServerAPI); });
function Expanded({ serverAPI, closeModal }: { serverAPI: ServerAPI; closeModal?: () => void }) {
  const [selected, select] = useState(lastSection);
  const [catalogue, setCatalogue] = useState<{ setName: string; tabs: StoreTabsContent["Tabs"] } | null>(null);
  const [failed, setFailed] = useState(false);
  const [revision, reload] = useState(0);
  useEffect(() => () => { modal = null; opening = false; }, []);
  useEffect(() => {
    let alive = true;
    setFailed(false);
    (async () => {
      try {
        const init = await executeAction<ExecuteArgs, ActionSet>(serverAPI, "MainMenu", "SkullKeyInit", { inputData: "" });
        const setName = init?.Content?.SetName;
        if (!setName) throw new Error("Missing store catalogue");
        const result = await executeAction<ExecuteArgs, StoreTabsContent>(serverAPI, setName, "GetContent", { inputData: "" });
        if (result?.Type !== "StoreTabs" || !Array.isArray(result.Content?.Tabs)) throw new Error("Invalid store catalogue");
        if (alive) setCatalogue({ setName, tabs: result.Content.Tabs });
      } catch { if (alive) setFailed(true); }
    })();
    return () => { alive = false; };
  }, [revision]);
  const settings = aboutPages(serverAPI, localStorage.getItem("sk_developermode") === "true").filter(p => p.visible !== false);
  const sections: ExpandedSection[] = [
    { id: "downloads", label: t("dl_title"), icon: <FaDownload /> },
    ...(catalogue?.tabs || []).map(tab => {
      const theme = storeTheme(tab.Title), Icon = theme.icon;
      return { id: "store:" + tab.ActionId, label: tabLabel(tab.Title), color: theme.color, icon: <Icon /> };
    }),
    ...settings.map((page, i) => ({ id: "settings:" + i, label: page.title as string, icon: <FaCog /> })),
  ];
  const valid = sections.some(s => s.id === selected);
  const current = valid || !catalogue ? selected : "downloads";
  const store = catalogue?.tabs.find(tab => "store:" + tab.ActionId === current);
  const setting = current.startsWith("settings:") ? settings[Number(current.slice(9))] : null;
  return <Modal closeModal={closeModal} onCancel={closeModal} bAllowFullSize>
    <ExpandedFrame brand="SkullKey" icon={<FaSkull />} sections={sections} selected={current}
      onSelect={id => { lastSection = id; select(id); }} onClose={() => closeModal?.()} closeLabel={t("view_close")}>
      {current === "downloads" ? <SkullKeyDownloads serverAPI={serverAPI} showEmpty embedded />
        : store && catalogue ? <Content key={store.ActionId} serverAPI={serverAPI} initActionSet={catalogue.setName} initAction={store.ActionId} />
        : setting ? setting.content : <Loading />}
      {failed && <ActionCard onClick={() => reload(v => v + 1)}>{t("free_refresh")}</ActionCard>}
    </ExpandedFrame>
  </Modal>;
}
export function openSkullKeyExpanded(serverAPI: ServerAPI) {
  if (opening || modal) return;
  opening = true;
  try { Navigation.CloseSideMenus(); modal = showModal(<Expanded serverAPI={serverAPI} />); }
  catch (error) { opening = false; console.error("[SkullKey] expanded view", error); }
}
export function closeSkullKeyExpanded() { deferredExpanded.cancel(); routeServerAPI = null; modal?.Close(); modal = null; opening = false; }
export function SkullKeyRoute({ serverAPI }: { serverAPI: ServerAPI }) {
  useEffect(() => {
    Navigation.NavigateBack();
    routeServerAPI = serverAPI;
    deferredExpanded.schedule();
  }, []);
  return null;
}
