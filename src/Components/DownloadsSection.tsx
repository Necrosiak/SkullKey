import { DialogButton, Focusable, ServerAPI } from "decky-frontend-lib";
import { VFC, useEffect, useState } from "react";
import { FaSkull, FaTimes } from "react-icons/fa";
import { storeTheme } from "./Styled";
import { t } from "../i18n";
import { QueueItem, getQueue, onQueueChange, removeFromQueue } from "../Utils/downloadQueue";

interface Dl { store: string; id: string; title: string; pct: number; desc: string }

// downloads.py store key -> name storeTheme understands (icon + colour).
const THEME: Record<string, string> = { ports: "classics", disks: "disks" };
const themeOf = (key: string) => storeTheme(THEME[key] || key);

// SkullKey's part of Steam's Downloads page: the game downloading now (big
// bar, like Steam's own header) and the games waiting their turn. Steam has
// no API to put non-Steam items in its own queue, so this sits above it.
export const SkullKeyDownloads: VFC<{ serverAPI: ServerAPI }> = ({ serverAPI }) => {
    const [active, setActive] = useState<Dl[]>([]);
    const [pending, setPending] = useState<QueueItem[]>([]);
    useEffect(() => {
        let alive = true;
        const poll = async () => {
            const r = await serverAPI.callPluginMethod<{}, Dl[]>("downloads_list", {});
            const q = await getQueue();
            if (!alive) return;
            if (r.success && Array.isArray(r.result)) setActive(r.result);
            setPending(q.pending);
        };
        poll();
        const timer = setInterval(poll, 2000);
        const off = onQueueChange(poll);
        return () => { alive = false; clearInterval(timer); off(); };
    }, []);
    if (!active.length && !pending.length) return null;
    const accent = storeTheme("classics").color;
    return (
        <div style={{ padding: "18px 24px 6px", background: "linear-gradient(180deg, rgba(200,162,75,0.10), transparent)" }}>
            <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 12 }}>
                <FaSkull size={26} color={accent} />
                <span style={{ fontSize: 22, fontWeight: 700, letterSpacing: ".5px" }}>SkullKey</span>
            </div>
            {active.map(d => {
                const th = themeOf(d.store);
                const Icon = th.icon;
                return (
                    <Focusable key={d.store + ":" + d.id} onActivate={() => { }} style={{ marginBottom: 12 }}>
                        <div style={{ display: "flex", alignItems: "center", gap: 10, fontSize: 17 }}>
                            <span style={{ color: th.color, display: "inline-flex" }}>{Icon && <Icon size={20} />}</span>
                            <span style={{ flex: 1 }}>{d.title}</span>
                            <span style={{ fontSize: 14, opacity: 0.85 }}>{Math.floor(d.pct)} %</span>
                        </div>
                        <div style={{ height: 6, borderRadius: 3, background: "rgba(255,255,255,0.12)", margin: "8px 0 6px" }}>
                            <div style={{ height: "100%", width: `${Math.min(100, Math.max(0, d.pct))}%`, borderRadius: 3,
                                          background: th.color, transition: "width .5s" }} />
                        </div>
                        <div style={{ fontSize: 12, opacity: 0.7 }} dangerouslySetInnerHTML={{ __html: d.desc }} />
                    </Focusable>
                );
            })}
            {!!pending.length && (
                <>
                    <div style={{ fontSize: 18, margin: "10px 0 8px", display: "flex", alignItems: "center", gap: 10 }}>
                        {t("queue_next")} <span style={{ opacity: 0.6 }}>({pending.length})</span>
                        <div style={{ flex: 1, height: 1, background: "rgba(255,255,255,0.15)" }} />
                    </div>
                    <Focusable style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                        {pending.map((q, i) => {
                            const th = storeTheme(q.set);
                            const Icon = th.icon;
                            return (
                                <Focusable key={q.set + ":" + q.shortname} flow-children="horizontal"
                                    style={{ display: "flex", alignItems: "center", gap: 10, padding: "8px 12px",
                                             borderRadius: 4, background: "rgba(255,255,255,0.05)", borderLeft: `3px solid ${th.color}` }}>
                                    <span style={{ opacity: 0.6, width: 18 }}>{i + 1}</span>
                                    <span style={{ color: th.color, display: "inline-flex" }}>{Icon && <Icon size={18} />}</span>
                                    <span style={{ flex: 1, fontSize: 16 }}>{q.name}</span>
                                    <DialogButton style={{ minWidth: 0, width: "auto", height: 30, padding: "0 12px", display: "flex",
                                                           alignItems: "center", gap: 6, fontSize: 12 }}
                                        onClick={() => removeFromQueue(q.set, q.shortname)}>
                                        <FaTimes size={11} /> {t("queue_remove")}
                                    </DialogButton>
                                </Focusable>
                            );
                        })}
                    </Focusable>
                </>
            )}
        </div>
    );
};
