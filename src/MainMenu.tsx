import { ModalRoot, Navigation, PanelSection, PanelSectionRow, ServerAPI, showModal } from "decky-frontend-lib";
import { VFC, useEffect, useState } from "react";
import { FaCog, FaStore } from "react-icons/fa";
import QRCode from "react-qr-code";
import { StoreContent, ContentType, StoreTabsContent, ExecuteArgs, ActionSet } from "./Types/Types";
import { executeAction } from "./Utils/executeAction";
import { ActionCard, storeTheme, ACCENT } from "./Components/Styled";
import { t, tabLabel } from "./i18n";

export const showQrModal = (url: string) => {
    showModal(
        <ModalRoot>
            <div
                style={{
                    margin: "0 auto 1.5em auto",
                    padding: "1em",
                    borderRadius: "2em",
                    background: "#F5F5F5",
                    boxShadow: "0 1em 2em rgba(0, 0, 0, 0.5)",
                }}
            >
                <QRCode value={url} size={256} fgColor="#000000" bgColor="#F5F5F5" />
            </div>
            <span style={{ textAlign: "center", wordBreak: "break-word" }}>
                {url}
            </span>
        </ModalRoot>,
        window,
    );
};

export const MainMenu: VFC<{ serverApi: ServerAPI; content: StoreContent; initActionSet: string; initAction: string; closeModal?: () => any }> = ({
    serverApi,
    content,
    initAction,
    initActionSet,
    closeModal }) => {
    const [storeTabs, setStoreTabs] = useState<{ Title: string; ActionId: string; Category?: string }[]>([]);

    // Resolve the store tabs (Epic / GOG / Amazon ...) so the panel can show
    // one colored card per store instead of a single generic button.
    useEffect(() => {
        (async () => {
            try {
                const init = await executeAction<ExecuteArgs, ActionSet>(serverApi, initActionSet, "SkullKeyInit", { inputData: "" });
                const setName = (init?.Content as ActionSet)?.SetName;
                if (!setName) return;
                const tabsRes = await executeAction<ExecuteArgs, ContentType>(serverApi, setName, "GetContent", { inputData: "" });
                if (tabsRes?.Type === "StoreTabs") {
                    setStoreTabs((tabsRes.Content as StoreTabsContent).Tabs ?? []);
                }
            } catch (e) {
                console.error("[SkullKey] store tabs fetch failed", e);
            }
        })();
    }, []);

    useEffect(() => {
        if (localStorage.getItem('sk_firstlaunch') != "false") {
            Navigation.CloseSideMenus();
            Navigation.Navigate("/about-skullkey");
            localStorage.setItem('sk_firstlaunch', 'false');
        }
    }, []);

    const openStore = (category?: string, tabIndex?: number) => {
        Navigation.CloseSideMenus();
        if (closeModal) closeModal();
        if (tabIndex !== undefined) {
            // pre-select the tab: the store page reads this key on mount. The
            // index is relative to the (category-filtered) tabs shown there.
            try {
                localStorage.setItem("sk_forced_tab", String(tabIndex));
            } catch (e) { }
        }
        const action = content.Panels?.[0]?.Actions?.[0]?.ActionId ?? "SkullKeyInit";
        const base = `/skullkey-content/${encodeURIComponent(initActionSet)}/${encodeURIComponent(action)}`;
        Navigation.Navigate(category ? `${base}/${encodeURIComponent(category)}` : base);
    };

    // Game stores (Epic/GOG/Amazon) and media/apps get their own menu so they
    // never share the store page's top bar.
    const gameTabs = storeTabs.filter((t) => (t.Category ?? "games") === "games");
    const mediaTabs = storeTabs.filter((t) => t.Category === "media");

    const renderCards = (group: typeof storeTabs, category: string) =>
        group.map((tab, index) => {
            const theme = storeTheme(tab.Title);
            const Icon = theme.icon;
            return (
                <PanelSectionRow key={tab.Title}>
                    <ActionCard big center={false} color={theme.color} onClick={() => openStore(category, index)}>
                        <Icon size={16} style={{ color: theme.color, flexShrink: 0 }} />
                        <span style={{ flex: 1, textAlign: "left", fontWeight: 600 }}>{tabLabel(tab.Title)}</span>
                        <span style={{ fontSize: 10, color: theme.color }}>▶</span>
                    </ActionCard>
                </PanelSectionRow>
            );
        });

    return (
        <>
            {storeTabs.length === 0 && (
                <PanelSection title={t("stores")}>
                    <PanelSectionRow>
                        <ActionCard big color={ACCENT} center={false} onClick={() => openStore()}>
                            <FaStore size={16} />
                            <span style={{ flex: 1, textAlign: "left" }}>{t("open_store")}</span>
                        </ActionCard>
                    </PanelSectionRow>
                </PanelSection>
            )}
            {gameTabs.length > 0 && (
                <PanelSection title={t("cat_games")}>
                    {renderCards(gameTabs, "games")}
                </PanelSection>
            )}
            {mediaTabs.length > 0 && (
                <PanelSection title={t("cat_media")}>
                    {renderCards(mediaTabs, "media")}
                </PanelSection>
            )}
            <PanelSection title={t("plugin")}>
                <PanelSectionRow>
                    <ActionCard color="#67a3ff" center={false} onClick={() => {
                        Navigation.CloseSideMenus();
                        if (closeModal) closeModal();
                        Navigation.Navigate("/about-skullkey");
                    }}>
                        <FaCog size={13} />
                        <span style={{ flex: 1, textAlign: "left" }}>{t("settings_about")}</span>
                    </ActionCard>
                </PanelSectionRow>
            </PanelSection>
        </>
    );
};
