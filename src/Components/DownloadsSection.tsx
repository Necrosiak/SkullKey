import { DialogButton, Focusable, ServerAPI } from "decky-frontend-lib";
import { VFC, useEffect, useState } from "react";
import { FaSkull, FaTimes } from "react-icons/fa";
import { storeTheme } from "./Styled";
import { t } from "../i18n";
import { QueueItem, getQueue, onQueueChange, removeFromQueue } from "../Utils/downloadQueue";
import { executeAction } from "../Utils/executeAction";

// downloads.py store key -> the store's action set (for its artwork).
const SET_OF: Record<string, string> = { xbox: "XboxActions", epic: "EpicActions", gog: "GOGActions", amazon: "AmazonActions",
    ea: "EAActions", mihoyo: "MiHoYoActions", ports: "PortsActions", disks: "DisksActions" };
const artCache: Record<string, { hero?: string; logo?: string }> = {};

const dataUri = (b64?: string | null, type?: string) => b64 ? `data:image/${type || "png"};base64,${b64}` : undefined;

// The game downloading now, drawn like Steam's own header: its hero art in
// the background, its logo on the left, the progress on the right.
const CurrentBanner: VFC<{ serverAPI: ServerAPI; d: Dl }> = ({ serverAPI, d }) => {
    const key = d.store + ":" + d.id;
    const [art, setArt] = useState(artCache[key] || {});
    useEffect(() => {
        if (artCache[key] || !SET_OF[d.store]) return;
        executeAction<any, any>(serverAPI, SET_OF[d.store], "GetJsonImages", { shortname: d.id }).then(r => {
            const c = r?.Content || {};
            artCache[key] = { hero: dataUri(c.Hero, c.HeroType) || dataUri(c.GridH, c.GridHType), logo: dataUri(c.Logo, c.LogoType) };
            setArt(artCache[key]);
        }).catch(() => { artCache[key] = {}; });
    }, [key]);
    const th = themeOf(d.store);
    const Icon = th.icon;
    const pct = Math.min(100, Math.max(0, d.pct));
    return (
        <Focusable onActivate={() => { }} style={{ position: "relative", height: 230, borderRadius: 4, overflow: "hidden",
            marginBottom: 12, background: "#0b0f14" }}>
            {art.hero && <img src={art.hero} style={{ position: "absolute", inset: 0, width: "100%", height: "100%", objectFit: "cover" }} />}
            <div style={{ position: "absolute", inset: 0,
                background: "linear-gradient(90deg, rgba(0,0,0,0.15) 0%, rgba(0,0,0,0.35) 45%, rgba(8,12,18,0.92) 62%, rgba(8,12,18,0.97) 100%)" }} />
            <div style={{ position: "absolute", left: 32, top: 0, bottom: 0, width: "40%", display: "flex", alignItems: "center" }}>
                {art.logo
                    ? <img src={art.logo} style={{ maxWidth: "100%", maxHeight: 130, objectFit: "contain", filter: "drop-shadow(0 2px 6px rgba(0,0,0,.6))" }} />
                    : <span style={{ fontSize: 34, fontWeight: 800, textShadow: "0 2px 8px rgba(0,0,0,.8)" }}>{d.title}</span>}
            </div>
            <div style={{ position: "absolute", right: 24, top: 0, bottom: 0, width: "40%", display: "flex", flexDirection: "column",
                justifyContent: "center", gap: 10 }}>
                <div style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 12, letterSpacing: ".5px", textTransform: "uppercase", opacity: 0.85 }}>
                    <span style={{ color: th.color, display: "inline-flex" }}>{Icon && <Icon size={16} />}</span>
                    <span>{d.title}</span>
                </div>
                <div>
                    <div style={{ display: "flex", justifyContent: "space-between", fontSize: 13, marginBottom: 6 }}>
                        <span>{t("dl_progress")}</span><span>{Math.floor(pct)} %</span>
                    </div>
                    <div style={{ height: 5, borderRadius: 3, background: "rgba(255,255,255,0.15)" }}>
                        <div style={{ height: "100%", width: `${pct}%`, borderRadius: 3, background: th.color, transition: "width .5s" }} />
                    </div>
                </div>
                <div style={{ fontSize: 12, opacity: 0.75 }} dangerouslySetInnerHTML={{ __html: d.desc }} />
            </div>
        </Focusable>
    );
};

interface Dl { store: string; id: string; title: string; pct: number; desc: string }

// downloads.py store key -> name storeTheme understands (icon + colour).
const THEME: Record<string, string> = { ports: "classics", disks: "disks" };
const themeOf = (key: string) => storeTheme(THEME[key] || key);

// SkullKey's part of Steam's Downloads page: the game downloading now (big
// bar, like Steam's own header) and the games waiting their turn. Steam has
// no API to put non-Steam items in its own queue, so this sits above it.
export const SkullKeyDownloads: VFC<{ serverAPI: ServerAPI; showEmpty?: boolean }> = ({ serverAPI, showEmpty }) => {
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
    if (!active.length && !pending.length)
        return showEmpty ? <div style={{ padding: "24px", opacity: 0.7, fontSize: 16 }}>{t("dl_none")}</div> : null;
    const accent = storeTheme("classics").color;
    return (
        <div style={{ padding: "18px 24px 6px", background: "linear-gradient(180deg, rgba(200,162,75,0.10), transparent)" }}>
            <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 12 }}>
                <FaSkull size={26} color={accent} />
                <span style={{ fontSize: 22, fontWeight: 700, letterSpacing: ".5px" }}>SkullKey</span>
            </div>
            {active.map(d => <CurrentBanner key={d.store + ":" + d.id} serverAPI={serverAPI} d={d} />)}
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

// SkullKey's own Downloads page (route /skullkey-downloads), opened from the
// download button of every store tab and from the queue notifications.
export const SkullKeyDownloadsPage: VFC<{ serverAPI: ServerAPI }> = ({ serverAPI }) => (
    <div style={{ marginTop: 40, height: "calc(100% - 40px)", overflowY: "auto", background: "#0e141b" }}>
        <SkullKeyDownloads serverAPI={serverAPI} showEmpty />
    </div>
);

export const DOWNLOADS_ROUTE = "/skullkey-downloads";
