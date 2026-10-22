import { DialogButton, Focusable, ModalRoot, ServerAPI } from "decky-frontend-lib";
import { VFC, useEffect, useState } from "react";
import { storeTheme } from "./Styled";
import { t } from "../i18n";

interface Dl { store: string; id: string; title: string; pct: number; desc: string }

// Store key from downloads.py -> name understood by storeTheme (icon + colour).
const THEME: Record<string, string> = { ports: "classics", disks: "disks", xbox: "xbox", epic: "epic", gog: "gog",
    amazon: "amazon", ea: "ea", mihoyo: "mihoyo" };

// Every download in progress, all stores together. Opened with the Select
// (View / Share / −) button from any SkullKey store tab.
export const DownloadsModal: VFC<{ serverAPI: ServerAPI; closeModal?: () => void }> = ({ serverAPI, closeModal }) => {
    const [items, setItems] = useState<Dl[] | null>(null);
    useEffect(() => {
        let alive = true;
        const poll = async () => {
            const r = await serverAPI.callPluginMethod<{}, Dl[]>("downloads_list", {});
            if (alive && r.success && Array.isArray(r.result)) setItems(r.result);
        };
        poll();
        const timer = setInterval(poll, 2000);
        return () => { alive = false; clearInterval(timer); };
    }, []);
    return (
        <ModalRoot onCancel={closeModal} closeModal={closeModal}>
            <div style={{ fontSize: 20, fontWeight: 700, marginBottom: 12 }}>{t("dl_title")}</div>
            {items === null && <div style={{ opacity: 0.7 }}>{t("inst_loading")}</div>}
            {items !== null && !items.length && <div style={{ opacity: 0.7 }}>{t("dl_none")}</div>}
            <Focusable style={{ display: "flex", flexDirection: "column", gap: 10 }}>
                {(items || []).map(d => {
                    const theme = storeTheme(THEME[d.store] || d.store);
                    const Icon = theme.icon;
                    return (
                        <Focusable key={d.store + ":" + d.id} focusable noFocusRing={false}
                            style={{ padding: "10px 12px", borderRadius: 6, background: "rgba(255,255,255,0.05)",
                                     borderLeft: `3px solid ${theme.color}` }}>
                            <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                                <span style={{ color: theme.color, display: "inline-flex" }}>{Icon && <Icon size={18} />}</span>
                                <span style={{ flex: 1, fontWeight: 600 }}>{d.title}</span>
                                <span style={{ fontSize: 13, opacity: 0.8 }}>{Math.floor(d.pct)} %</span>
                            </div>
                            <div style={{ height: 6, borderRadius: 3, background: "rgba(255,255,255,0.1)", margin: "8px 0 6px" }}>
                                <div style={{ height: "100%", width: `${Math.min(100, Math.max(0, d.pct))}%`,
                                              borderRadius: 3, background: theme.color, transition: "width .5s" }} />
                            </div>
                            <div style={{ fontSize: 12, opacity: 0.7 }} dangerouslySetInnerHTML={{ __html: d.desc }} />
                        </Focusable>
                    );
                })}
            </Focusable>
            <div style={{ display: "flex", justifyContent: "flex-end", marginTop: 14 }}>
                <DialogButton style={{ width: "auto", minWidth: 0, padding: "0 20px" }} onClick={closeModal}>{t("dl_close")}</DialogButton>
            </div>
        </ModalRoot>
    );
};
