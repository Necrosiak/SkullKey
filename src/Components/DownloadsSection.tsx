import { DialogButton, Focusable, Navigation, ServerAPI } from "decky-frontend-lib";
import React, { VFC, useEffect, useState } from "react";
import { FaSkull, FaTimes, FaDownload, FaPause, FaPlay } from "react-icons/fa";
import { storeTheme } from "./Styled";
import { t } from "../i18n";
import { QueueItem, SET_OF, getQueue, onQueueChange, prioritize, removeCurrent, removeFromQueue, setPaused } from "../Utils/downloadQueue";
import { executeAction } from "../Utils/executeAction";

interface Dl { store: string; id: string; title: string; pct: number; desc: string; dest?: string; paused?: boolean }

// downloads.py store key -> name storeTheme understands (icon + colour) and
// the store's action set (for its artwork).
const THEME: Record<string, string> = { ports: "classics", disks: "disks" };
const themeOf = (key: string) => storeTheme(THEME[key] || key);

// Artwork per game, fetched once (the stores cache it on disk too).
type Art = { hero?: string; logo?: string; capsule?: string };
const artCache: Record<string, Art> = {};
const artPending: Record<string, Promise<Art>> = {};
const dataUri = (b64?: string | null, type?: string) => b64 ? `data:image/${type || "png"};base64,${b64}` : undefined;
function useArt(serverAPI: ServerAPI, set: string | undefined, shortname: string): Art {
    const key = (set || "") + ":" + shortname;
    const [art, setArt] = useState<Art>(artCache[key] || {});
    useEffect(() => {
        if (artCache[key] || !set) return;
        artPending[key] = artPending[key] || executeAction<any, any>(serverAPI, set, "GetJsonImages", { shortname }).then(r => {
            const c = r?.Content || {};
            return artCache[key] = {
                hero: dataUri(c.Hero, c.HeroType) || dataUri(c.GridH, c.GridHType),
                // Only a real (transparent PNG) logo: Xbox puts a JPG box art there.
                logo: c.Logo && (c.LogoType || "png").toLowerCase() === "png" ? dataUri(c.Logo, "png") : undefined,
                capsule: dataUri(c.GridH, c.GridHType) || dataUri(c.Hero, c.HeroType) || dataUri(c.Grid, c.GridType),
            };
        }).catch(() => artCache[key] = {});
        artPending[key].then(a => setArt(a));
    }, [key]);
    return art;
}

// Speed and amounts as the stores write them ("12,6 / 120,1 Go · 48 Mo/s").
const num = (s: string) => parseFloat(s.replace(",", "."));
function parseDesc(desc: string) {
    const plain = desc.replace(/<[^>]+>/g, " ");
    const sp = plain.match(/([\d.,]+)\s*(Mo|MB|MiB|Go|GB|GiB)\/s/i);
    const speed = sp ? num(sp[1]) * (/^g/i.test(sp[2]) ? 1024 : 1) : null;  // MB/s
    const am = plain.match(/([\d.,]+)\s*(Mo|MB|MiB|Go|GB|GiB)?\s*\/\s*([\d.,]+)\s*(Mo|MB|MiB|Go|GB|GiB)/i);
    // Both sides with their unit, like Steam ("28,8 Go / 120,1 Go").
    const unit = (u?: string) => (u || "").replace(/^(MiB|MB)$/i, "Mo").replace(/^(GiB|GB)$/i, "Go");
    const amount = am ? `${am[1]} ${unit(am[2] || am[4])} / ${am[3]} ${unit(am[4])}` : null;
    const eta = plain.match(/~\s*([\d]+\s*(?:min|h|s)[^·]*)/i);
    return { speed, amount, eta: eta ? eta[1].trim() : null };
}

// Speed history per download (2 s samples), kept across re-renders.
const HISTORY = 60;
const history: Record<string, number[]> = {};

const BTN = { minWidth: 0, width: "auto", height: 32, padding: "0 14px", display: "flex", alignItems: "center", gap: 6, fontSize: 12 };

const Stat: VFC<{ label: string; value: string; color: string }> = ({ label, value, color }) => (
    <div style={{ flex: 1 }}>
        <div style={{ fontSize: 10, letterSpacing: ".5px", textTransform: "uppercase", opacity: 0.75, display: "flex", alignItems: "center", gap: 6 }}>
            <span style={{ width: 10, height: 3, background: color, display: "inline-block" }} />{label}
        </div>
        <div style={{ fontSize: 14, fontWeight: 600, marginTop: 3 }}>{value}</div>
    </div>
);

const Bar: VFC<{ label: string; right: string; pct: number; color: string }> = ({ label, right, pct, color }) => (
    <div>
        <div style={{ display: "flex", justifyContent: "space-between", fontSize: 13, marginBottom: 5 }}>
            <span>{label}</span><span style={{ opacity: 0.85 }}>{right}</span>
        </div>
        <div style={{ height: 4, background: "rgba(255,255,255,0.15)" }}>
            <div style={{ height: "100%", width: `${Math.min(100, Math.max(0, pct))}%`, background: color, transition: "width .5s" }} />
        </div>
    </div>
);

// The game downloading now, drawn like Steam's own header: hero art and logo
// on the left, a speed graph in the middle, stats and bars on the right.
const CurrentBanner: VFC<{ serverAPI: ServerAPI; d: Dl }> = ({ serverAPI, d }) => {
    const key = d.store + ":" + d.id;
    const art = useArt(serverAPI, SET_OF[d.store], d.id);
    // A logo is wide; a square/portrait "logo" is box art (Xbox): use the title.
    const [logoOk, setLogoOk] = useState<boolean | null>(null);
    const th = themeOf(d.store);
    const Icon = th.icon;
    const parsed = parseDesc(d.desc);
    const { amount, eta } = parsed;
    const speed = d.paused ? 0 : parsed.speed;
    const h = history[key] = history[key] || [];
    if (speed !== null && (h.length === 0 || (h as any).last !== d.desc)) {
        h.push(speed);
        if (h.length > HISTORY) h.shift();
        (h as any).last = d.desc;
    }
    const peak = Math.max(1, ...h);
    const dest = d.dest === "System" ? t("dl_system_drive") : (d.dest || "—");
    // Two phases like Steam: data first (blue), then installing (green) once
    // the store reports an install / extract / verify step.
    const installing = /install|extract|v[ée]rif|d[ée]compress|unpack|[ée]tape 4\/4|step 4\/4/i.test(d.desc.replace(/<[^>]+>/g, " "));
    const dataPct = installing ? 100 : d.pct;
    const installPct = installing ? d.pct : 0;
    return (
        <div style={{ position: "relative", height: 250, overflow: "hidden", background: "#10161d" }}>
            {art.hero && <img src={art.hero} style={{ position: "absolute", left: 0, top: 0, height: "100%", width: "62%", objectFit: "cover" }} />}
            <div style={{ position: "absolute", inset: 0,
                background: "linear-gradient(90deg, rgba(0,0,0,0) 0%, rgba(0,0,0,0.25) 35%, rgba(16,22,29,0.85) 55%, #10161d 62%)" }} />
            {/* speed graph, between the art and the stats */}
            <svg viewBox={`0 0 ${HISTORY} 100`} preserveAspectRatio="none"
                style={{ position: "absolute", left: "30%", width: "25%", bottom: 0, height: "75%" }}>
                {h.map((v, i) => (
                    <rect key={i} x={HISTORY - h.length + i + 0.15} width={0.7} y={100 - (v / peak) * 95} height={(v / peak) * 95}
                        fill="#2f7fd0" opacity={0.85} />
                ))}
                <polyline fill="none" stroke="#5bd35b" strokeWidth={1.2} vectorEffect="non-scaling-stroke"
                    points={h.map((v, i) => `${HISTORY - h.length + i + 0.5},${100 - (v / peak) * 95}`).join(" ")} />
            </svg>
            <div style={{ position: "absolute", left: 40, top: 0, bottom: 34, width: "26%", display: "flex", alignItems: "center" }}>
                {art.logo && logoOk !== false
                    ? <img src={art.logo} onLoad={e => setLogoOk(e.currentTarget.naturalWidth >= 1.6 * e.currentTarget.naturalHeight)}
                        style={{ maxWidth: "100%", maxHeight: 120, objectFit: "contain", filter: "drop-shadow(0 2px 6px rgba(0,0,0,.7))",
                                 visibility: logoOk ? "visible" : "hidden" }} />
                    : <span style={{ fontSize: 30, fontWeight: 800, textShadow: "0 2px 8px rgba(0,0,0,.9)" }}>{d.title}</span>}
            </div>
            <div style={{ position: "absolute", left: 12, bottom: 12, padding: "4px 10px", background: "rgba(0,0,0,0.65)", fontSize: 12,
                display: "flex", alignItems: "center", gap: 6, letterSpacing: ".3px", textTransform: "uppercase" }}>
                {d.title}<span style={{ color: th.color, display: "inline-flex" }}>{Icon && <Icon size={13} />}</span>
            </div>
            <div style={{ position: "absolute", right: 24, top: 0, bottom: 0, width: "40%", display: "flex", flexDirection: "column",
                justifyContent: "center", gap: 16 }}>
                <div style={{ display: "flex", gap: 12 }}>
                    <Stat label={t("dl_network")} value={speed !== null ? `${speed.toFixed(1)} Mo/s` : "—"} color="#2f7fd0" />
                    <Stat label={t("dl_peak")} value={h.length ? `${peak.toFixed(1)} Mo/s` : "—"} color="#2f7fd0" />
                    <Stat label={t("dl_destination")} value={dest} color="#5bd35b" />
                </div>
                <Bar label={t("dl_data")} right={amount ? `${amount}  ·  ${Math.floor(dataPct)} %` : `${Math.floor(dataPct)} %`} pct={dataPct} color="#2f7fd0" />
                <Bar label={t("dl_install")} right={`${Math.floor(installPct)} %`} pct={installPct} color="#5bd35b" />
                <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                    <div style={{ flex: 1, fontSize: 12, opacity: 0.7 }}>
                        {d.paused ? t("dl_paused") : (eta ? t("dl_eta", { eta }) : "")}
                    </div>
                    <Focusable flow-children="horizontal" navEntryPreferPosition={2} style={{ display: "flex", gap: 8 }}>
                        <DialogButton style={BTN} onClick={() => setPaused(SET_OF[d.store], d.id, !d.paused)}>
                            {d.paused ? <FaPlay size={11} /> : <FaPause size={11} />} {d.paused ? t("dl_resume") : t("dl_pause")}
                        </DialogButton>
                        <DialogButton style={BTN} onClick={() => removeCurrent(SET_OF[d.store], d.id)}>
                            <FaTimes size={11} /> {t("queue_remove")}
                        </DialogButton>
                    </Focusable>
                </div>
            </div>
        </div>
    );
};

const QueueRow: VFC<{ serverAPI: ServerAPI; q: QueueItem; i: number }> = ({ serverAPI, q, i }) => {
    const art = useArt(serverAPI, q.set, q.shortname);
    const th = storeTheme(q.set);
    const Icon = th.icon;
    return (
        // Up/down keep the column (Remove -> Remove), like Steam's lists.
        <Focusable flow-children="horizontal" navEntryPreferPosition={2}
            style={{ display: "flex", alignItems: "center", gap: 16, padding: "6px 0" }}>
            <div style={{ position: "relative", width: 140, height: 52, flexShrink: 0, background: "#1b232c", overflow: "hidden" }}>
                {art.capsule && <img src={art.capsule} style={{ width: "100%", height: "100%", objectFit: "cover" }} />}
            </div>
            <div style={{ flex: 1 }}>
                <div style={{ fontSize: 18, display: "flex", alignItems: "center", gap: 10 }}>
                    {q.name}<span style={{ color: th.color, display: "inline-flex" }}>{Icon && <Icon size={16} />}</span>
                </div>
                <div style={{ fontSize: 11, opacity: 0.6, letterSpacing: ".4px", textTransform: "uppercase" }}>
                    {q.paused ? t("dl_paused") : t("queue_position", { n: i + 1 })}
                </div>
            </div>
            <DialogButton style={BTN} onClick={() => prioritize(q)}>
                <FaDownload size={11} /> {t("dl_now")}
            </DialogButton>
            <DialogButton style={BTN} onClick={() => removeFromQueue(q.set, q.shortname)}>
                <FaTimes size={11} /> {t("queue_remove")}
            </DialogButton>
        </Focusable>
    );
};

// SkullKey downloads: the game downloading now and the games waiting.
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
    const accent = storeTheme("classics").color;
    const header = (
        <div style={{ display: "flex", alignItems: "center", gap: 10, padding: "16px 24px 12px" }}>
            <FaSkull size={24} color={accent} />
            <span style={{ fontSize: 22, fontWeight: 700 }}>SkullKey</span>
            <span style={{ fontSize: 15, opacity: 0.6, display: "flex", alignItems: "center", gap: 6 }}><FaDownload size={12} /> {t("dl_title")}</span>
        </div>
    );
    if (!active.length && !pending.length)
        return showEmpty ? <div>{header}<div style={{ padding: "8px 24px", opacity: 0.7, fontSize: 16 }}>{t("dl_none")}</div></div> : null;
    return (
        <div>
            {header}
            {active.map(d => <CurrentBanner key={d.store + ":" + d.id} serverAPI={serverAPI} d={d} />)}
            <div style={{ padding: "14px 24px" }}>
                <div style={{ fontSize: 20, margin: "4px 0 8px", display: "flex", alignItems: "center", gap: 10 }}>
                    {t("queue_next")} <span style={{ opacity: 0.6 }}>({pending.length})</span>
                    <div style={{ flex: 1, height: 1, background: "rgba(255,255,255,0.15)" }} />
                </div>
                {!pending.length && <div style={{ opacity: 0.6, fontSize: 15 }}>{t("queue_empty")}</div>}
                <Focusable style={{ display: "flex", flexDirection: "column" }}>
                    {pending.map((q, i) => <QueueRow key={q.set + ":" + q.shortname} serverAPI={serverAPI} q={q} i={i} />)}
                </Focusable>
            </div>
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

// Top bar indicator, like Steam's own download icon: shown while SkullKey
// downloads, a skull that fills from the bottom with the whole job (download
// + install). It is placed INSIDE Steam's row of top bar icons (a portal in
// front of the first icon), so it lines up and never overlaps them; the spot
// is checked again on every poll in case Steam redraws its bar.
// Plugin code runs in Steam's shared JS context: `document` there is not the
// Big Picture window. The window's own document comes from a rendered node.
function topBarHolder(doc: Document): HTMLElement | null {
    const win = doc.defaultView || window;
    const existing = doc.querySelector("[data-sk-topbar]") as HTMLElement | null;
    if (existing && existing.isConnected) return existing;
    const icons = [...doc.querySelectorAll("svg")]
        .filter(e => { const b = e.getBoundingClientRect(); return b.top >= 0 && b.top < 45 && b.width >= 14 && b.left > win.innerWidth / 2; })
        .sort((a, b) => a.getBoundingClientRect().left - b.getBoundingClientRect().left);
    if (!icons.length) return null;
    // climb from the leftmost icon to the row that holds several icons
    let item: HTMLElement = icons[0] as unknown as HTMLElement;
    while (item.parentElement && item.parentElement.querySelectorAll("svg").length < 3) item = item.parentElement;
    const row = item.parentElement;
    if (!row) return null;
    // Insert before the first visible icon button on the right half (the
    // search icon, or Steam's own download icon when it shows).
    const first = ([...row.children] as HTMLElement[]).find(c => {
        const b = c.getBoundingClientRect();
        return b.width > 20 && b.width < 120 && b.left > win.innerWidth / 2;
    });
    if (first) item = first;
    const holder = doc.createElement("div");
    holder.setAttribute("data-sk-topbar", "");
    holder.style.cssText = "display:flex;align-items:center;justify-content:center;cursor:pointer";
    row.insertBefore(holder, item);
    return holder;
}

// Steam hands each panel's navigation node down through a React context. Re-
// providing the top bar row's node around our button makes it a child of that
// row in the controller navigation, like Steam's own icons (no Steam code is
// modified; if the context is not found the icon stays touch-only).
function rowNavContext(row: HTMLElement): { type: any; value: any } | null {
    const fk = Object.keys(row).find(k => k.startsWith("__reactFiber"));
    let f = fk ? (row as any)[fk] : null;
    for (let i = 0; i < 12 && f; i++, f = f.return) {
        const v = f.memoizedProps?.value;
        if (v && v.m_element === row && f.type) return { type: f.type, value: v };
    }
    return null;
}

// Our node joins the row last; put it where it sits on screen so left/right
// reach it between Steam's icons.
function sortRowNav(holder: HTMLElement) {
    const row = holder.parentElement;
    const nav = row ? rowNavContext(row) : null;
    const kids: any[] | undefined = nav?.value?.m_rgChildren;
    if (!kids || !kids.some(c => holder.contains(c.m_element))) return;
    const before = kids.map(c => c);
    kids.sort((a, b) => (a.m_element && b.m_element && (a.m_element.compareDocumentPosition(b.m_element) & 4)) ? -1 : 1);
    if (kids.some((c, i) => c !== before[i]) && nav!.value.m_iLastActiveChildIndex !== undefined) nav!.value.m_iLastActiveChildIndex = -1;
}

export const TopBarDownloads: VFC<{ serverAPI: ServerAPI }> = ({ serverAPI }) => {
    const [focused, setFocused] = useState(false);
    const [d, setD] = useState<Dl | null>(null);
    const [count, setCount] = useState(0);
    const [holder, setHolder] = useState<HTMLElement | null>(null);
    const [anchor, setAnchor] = useState<HTMLSpanElement | null>(null);
    useEffect(() => {
        if (!anchor) return;
        const doc = anchor.ownerDocument;
        let alive = true;
        const poll = async () => {
            const r = await serverAPI.callPluginMethod<{}, Dl[]>("downloads_list", {});
            const q = await getQueue();
            if (!alive) return;
            const list = r.success && Array.isArray(r.result) ? r.result : [];
            setD(list[0] || null);
            setCount(list.length + q.pending.length);
            if (list.length) {
                const h = topBarHolder(doc);
                setHolder(h);
                if (h) setTimeout(() => sortRowNav(h), 300);
            }
            else { doc.querySelector("[data-sk-topbar]")?.remove(); setHolder(null); }
        };
        poll();
        const timer = setInterval(poll, 3000);
        return () => { alive = false; clearInterval(timer); doc.querySelector("[data-sk-topbar]")?.remove(); };
    }, [anchor]);
    const probe = <span ref={setAnchor} style={{ display: "none" }} />;
    if (!d || !holder) return probe;
    // Whole job: with steps ("Étape 3/4"), count the finished steps too.
    const step = d.desc.replace(/<[^>]+>/g, " ").match(/(?:[ée]tape|step)\s*(\d+)\s*\/\s*(\d+)/i);
    const raw = Math.min(100, Math.max(0, d.pct));
    const pct = step ? ((Number(step[1]) - 1) + raw / 100) / Number(step[2]) * 100 : raw;
    const createPortal = (window as any).SP_REACTDOM?.createPortal;
    if (!createPortal) return probe;
    const nav = holder.parentElement ? rowNavContext(holder.parentElement) : null;
    const open = () => Navigation.Navigate(DOWNLOADS_ROUTE);
    // Like Steam's download icon: the icon, and a thin blue line under it
    // that fills with the game being downloaded.
    const button = (
        <Focusable onActivate={open} onClick={open} noFocusRing
            onGamepadFocus={() => setFocused(true)} onGamepadBlur={() => setFocused(false)}
            style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 3, padding: "6px 8px",
                     background: focused ? "#ffffff" : "transparent", borderRadius: 2 }}>
            <FaSkull size={20} color={focused ? "#0e141b" : (d.paused ? "#9aa4b2" : "#ffffff")} />
            <div style={{ width: 22, height: 2, background: "rgba(127,127,127,0.35)" }}>
                <div style={{ width: `${pct}%`, height: "100%", background: d.paused ? "#9aa4b2" : "#1a9fff", transition: "width .5s" }} />
            </div>
        </Focusable>
    );
    return <>{probe}{createPortal(nav ? React.createElement(nav.type, { value: nav.value }, button) : button, holder)}</>;
};
