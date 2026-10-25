import { ServerAPI } from "decky-frontend-lib";
import { executeAction } from "./executeAction";
import Logger from "./logger";

// Steam UI globals (present at runtime in the Steam JS context).
declare const appStore: any, collectionStore: any;

const logger = new Logger("collections");

// Every installed SkullKey game sits in the Steam collection named after its
// store ("Epic", "Xbox", ...), so the library groups them and each collection
// shows their artwork. Games installed before this existed (or by a path that
// skipped it) are added here; duplicate collections SkullKey made under the
// same name are merged into one.
export async function syncCollections(serverAPI: ServerAPI) {
    try {
        const res = await serverAPI.callPluginMethod<{}, any[]>("platforms_get", {});
        const platforms = (res.success && Array.isArray(res.result) ? res.result : [])
            .filter((p: any) => p.enabled);
        const init = await executeAction<any, any>(serverAPI, "MainMenu", "SkullKeyInit", { inputData: "" });
        const root = init?.Content?.SetName;
        if (!root) return;
        for (const p of platforms) {
            try {
                const set = (await executeAction<any, any>(serverAPI, root, p.ActionId, {}))?.Content?.SetName;
                if (!set) continue;
                const content = await executeAction<any, any>(serverAPI, set, "GetContent",
                    { filter: "", installed: "true", limited: "false" });
                const ids = ((content?.Content?.Games ?? []) as any[])
                    .map(g => parseInt(String(g.SteamClientID)))
                    .filter(id => id > 0 && appStore.GetAppOverviewByAppID(id));
                await fill(set.replace(/Actions$/, ""), ids);
            } catch (e) { logger.error("store", p.ActionId, e); }  // one store never stops the others
        }
    } catch (e) {
        logger.error("sync", e);
    }
}

async function fill(name: string, ids: number[]) {
    const same = collectionStore.userCollections.filter((c: any) => c.displayName === name && String(c.id).startsWith("uc-"));
    let col = same[0];
    // merge SkullKey's own duplicates (same name) into the first one
    for (const dup of same.slice(1)) {
        const apps = dup.allApps || [];
        if (apps.length && col.AsDragDropCollection) col.AsDragDropCollection().AddApps(apps);
        await col.Save();
        if (dup.Delete) await dup.Delete();
    }
    if (!ids.length) return;
    if (!col) {
        col = collectionStore.NewUnsavedCollection(name, undefined, []);
        await col.Save();
    }
    const have = new Set((col.allApps || []).map((a: any) => a.appid));
    const missing = ids.filter(id => !have.has(id)).map(id => appStore.GetAppOverviewByAppID(id)).filter(Boolean);
    if (missing.length && col.AsDragDropCollection) {
        col.AsDragDropCollection().AddApps(missing);
        await col.Save();
        logger.log(`collection ${name}: +${missing.length}`);
    }
}
