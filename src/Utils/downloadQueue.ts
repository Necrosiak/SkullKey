import { Navigation, ServerAPI } from "decky-frontend-lib";
import { executeAction } from "./executeAction";
import { configureShortcut } from "./utils";
import { notify } from "../Components/Styled";
import { t } from "../i18n";
import Logger from "./logger";

// One download at a time, whatever the store: games installed while another
// one downloads wait in this queue and start by themselves, in order. The
// queue lives in the backend (download_queue.json) so it survives a plugin
// reload; this runner drives it from the Steam UI, because creating the Steam
// shortcut at the end needs SteamClient.

export interface QueueItem { set: string; shortname: string; name: string; drive: string; update?: boolean; paused?: boolean }

// action set <-> store key used by scripts/downloads.py
export const STORE_OF: Record<string, string> = { XboxActions: "xbox", EpicActions: "epic", GOGActions: "gog",
    AmazonActions: "amazon", EAActions: "ea", MiHoYoActions: "mihoyo", PortsActions: "ports", DisksActions: "disks" };
export const SET_OF: Record<string, string> = Object.fromEntries(Object.entries(STORE_OF).map(([k, v]) => [v, k]));

async function control(set: string, shortname: string, action: "pause" | "resume") {
    const r = await api!.callPluginMethod<any, boolean>("download_control", { store: STORE_OF[set], gid: shortname, action });
    return r.success && !!r.result;
}

/** Pause / resume the download running now (any store). */
export async function setPaused(set: string, shortname: string, paused: boolean) {
    if (!api) return;
    await control(set, shortname, paused ? "pause" : "resume");
    const state = await load();
    if (state.current && state.current.set === set && state.current.shortname === shortname) {
        state.current = { ...state.current, paused };
        await save(state);
    } else listeners.forEach(l => l());
}

/** Stop and remove the download running now; the next one starts. */
export async function removeCurrent(set: string, shortname: string) {
    if (!api) return;
    await control(set, shortname, "resume");  // a frozen process cannot stop
    await executeAction<any, any>(api, set, "CancelInstall", { shortname });
    await cancelCurrent(set, shortname);
    await tick();
}

/** "Download now" on a waiting game: the running one pauses and waits first in line. */
export async function prioritize(item: QueueItem) {
    if (!api) return;
    const state = await load();
    const same = (q: QueueItem) => q.set === item.set && q.shortname === item.shortname;
    state.pending = state.pending.filter(q => !same(q));
    if (state.current) {
        await control(state.current.set, state.current.shortname, "pause");
        state.pending.unshift({ ...state.current, paused: true });
    }
    state.current = { ...item, paused: false };
    await save(state);
    // A paused game resumes in place; if its process is gone, the download
    // starts again over the files already on disk.
    if (item.paused && await control(item.set, item.shortname, "resume")) return;
    if (!(await start(item))) {
        notify({ title: "SkullKey", body: t("queue_failed", { game: item.name }) });
        state.current = null;
        await save(state);
    }
}
interface QueueState { current: QueueItem | null; pending: QueueItem[] }

// Steam UI globals (present at runtime in the Steam JS context).
declare const appStore: any, appDetailsCache: any, appDetailsStore: any, settingsStore: any, collectionStore: any;

const logger = new Logger("downloadQueue");
let api: ServerAPI | null = null;
let busy = false;
const listeners = new Set<() => void>();

// Stores that install through their own client (shown to the player) stay
// outside the queue.
export const QUEUEABLE = /^(Epic|GOG|Xbox|Amazon|EA|MiHoYo|Ports|Disks)Actions$/;

async function load(): Promise<QueueState> {
    const r = await api!.callPluginMethod<{}, QueueState>("queue_get", {});
    return r.success && r.result ? r.result : { current: null, pending: [] };
}

async function save(state: QueueState) {
    await api!.callPluginMethod("queue_set", { state });
    listeners.forEach(l => l());
}

export function onQueueChange(cb: () => void) {
    listeners.add(cb);
    return () => { listeners.delete(cb); };
}

export async function getQueue(): Promise<QueueState> {
    return api ? load() : { current: null, pending: [] };
}

/** Adds a game. Returns 0 when it starts now, else its place in line. */
export async function enqueue(item: QueueItem): Promise<number> {
    const state = await load();
    const same = (q: QueueItem) => q.set === item.set && q.shortname === item.shortname;
    if ((state.current && same(state.current)) || state.pending.some(same)) {
        return state.current && same(state.current) ? 0 : state.pending.findIndex(same) + 1;
    }
    state.pending.push(item);
    await save(state);
    await tick();
    const after = await load();
    return after.current && same(after.current) ? 0 : after.pending.findIndex(same) + 1;
}

export async function removeFromQueue(set: string, shortname: string) {
    const state = await load();
    state.pending = state.pending.filter(q => !(q.set === set && q.shortname === shortname));
    await save(state);
}

/** The game page's Cancel: drop the running item and move on. */
export async function cancelCurrent(set: string, shortname: string) {
    const state = await load();
    if (state.current && state.current.set === set && state.current.shortname === shortname) {
        state.current = null;
        await save(state);
    }
}

async function start(item: QueueItem): Promise<boolean> {
    await api!.callPluginMethod("set_install_root", { path: item.drive || "" });
    const res = await executeAction<any, any>(api!, item.set, item.update ? "Update" : "Download", { shortname: item.shortname });
    return res?.Type === "Progress";
}

// Steam shortcut + launch options + artwork + store collection, the same
// steps the game page does when it watches an install to the end.
export async function finishInstall(serverAPI: ServerAPI, set: string, shortname: string, name: string) {
    const SHORTCUT = 1073741824;
    let id = appStore.allApps.find((a: any) => a.app_type == SHORTCUT && a.display_name == name)?.appid;
    if (!id) {
        id = await SteamClient.Apps.AddShortcut("Name", "/bin/bash", "", "");
        await appDetailsCache.FetchDataForApp(id);
        await appDetailsStore.RequestAppDetails(id);
        SteamClient.Apps.SetShortcutName(id, name);
    }
    const res = await executeAction<any, any>(serverAPI, set, "Install", { shortname, steamClientID: String(id) });
    if (res?.Type === "LaunchOptions") {
        const lo = res.Content;
        configureShortcut(id, lo);
        SteamClient.Apps.SetShortcutName(id, name);
        if (lo.Compatibility) {
            const def = settingsStore.settings.strCompatTool;
            if (def) SteamClient.Apps.SpecifyCompatTool(id, def);
            else {
                const tools = await SteamClient.Apps.GetAvailableCompatTools(1);
                const tool = tools.find((x: any) => x.strToolName.startsWith("proton") && x.strToolName.indexOf("experimental") == -1);
                if (tool) SteamClient.Apps.SpecifyCompatTool(id, tool.strToolName);
            }
        } else SteamClient.Apps.SpecifyCompatTool(id, "");
    }
    try {
        const img = (await executeAction<any, any>(serverAPI, set, "GetJsonImages", { shortname }))?.Content;
        if (img) {
            if (img.Grid) await SteamClient.Apps.SetCustomArtworkForApp(id, img.Grid, img.GridType || "png", 0);
            if (img.Hero) await SteamClient.Apps.SetCustomArtworkForApp(id, img.Hero, img.HeroType || "png", 1);
            if (img.Logo) await SteamClient.Apps.SetCustomArtworkForApp(id, img.Logo, img.LogoType || "png", 2);
            if (img.GridH) await SteamClient.Apps.SetCustomArtworkForApp(id, img.GridH, img.GridHType || "png", 3);
        }
    } catch (e) { logger.error("artwork", e); }
    try {
        const storeName = set.replace(/Actions$/, "");
        let col = collectionStore.userCollections.find((c: any) => c.displayName === storeName);
        if (!col) { col = collectionStore.NewUnsavedCollection(storeName, undefined, []); await col.Save(); }
        const ov = appStore.GetAppOverviewByAppID(id);
        if (ov && col.AsDragDropCollection) { col.AsDragDropCollection().AddApps([ov]); await col.Save(); }
    } catch (e) { logger.error("collection", e); }
    return id;
}

async function tick() {
    if (!api || busy) return;
    busy = true;
    try {
        const state = await load();
        if (state.current?.paused) return;  // paused by the player: the line waits
        if (state.current) {
            const p = (await executeAction<any, any>(api, state.current.set, "GetProgress", { shortname: state.current.shortname }))?.Content;
            if (p?.Error) {
                notify({ title: "SkullKey", body: t("queue_failed", { game: state.current.name }) });
                state.current = null;
                await save(state);
            } else if (p && p.Percentage >= 100) {
                const done = state.current;
                state.current = null;
                await save(state);
                const id = await finishInstall(api, done.set, done.shortname, done.name);
                notify({
                    title: "SkullKey", body: t("queue_done", { game: done.name }), clickKey: `queue-done:${done.set}:${done.shortname}`,
                    onClick: () => { Navigation.CloseSideMenus(); Navigation.Navigate(`/library/app/${id}`); },
                });
            }
            return;
        }
        // Something started outside the queue (an update from the game page,
        // an auto-update) keeps the line waiting too.
        const running = await api.callPluginMethod<{}, any[]>("downloads_list", {});
        if (running.success && Array.isArray(running.result) && running.result.some((d: any) => !d.paused)) return;
        const next = state.pending.shift();
        if (!next) return;
        state.current = { ...next, paused: false };
        await save(state);
        if (next.paused && await control(next.set, next.shortname, "resume")) return;  // thawed in place
        if (!(await start(next))) {
            notify({ title: "SkullKey", body: t("queue_failed", { game: next.name }) });
            state.current = null;
            await save(state);
        }
    } catch (e) {
        logger.error("tick", e);
    } finally {
        busy = false;
    }
}

export function startQueueRunner(serverAPI: ServerAPI): () => void {
    api = serverAPI;
    tick();
    const timer = setInterval(tick, 3000);
    return () => clearInterval(timer);
}
