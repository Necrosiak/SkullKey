// Settings pages: installed games of every platform, and switching platforms
// on or off. Both reuse the store plumbing: the store's own GetContent with
// installed=true, and the game page every tab already opens.
import { DialogButton, Focusable, ServerAPI, ToggleField, showModal } from "decky-frontend-lib";
import { VFC, useEffect, useState } from "react";
import { ActionSet, ExecuteArgs, ExecuteGetContentArgs, ContentResult, ContentType, GameDataList } from "../Types/Types";
import { executeAction } from "../Utils/executeAction";
import { GameDetailsItem } from "./GameDetailsItem";
import { pickInstallDrive } from "./DrivePicker";
import { notify, storeTheme } from "./Styled";
import { t, tabLabel } from "../i18n";
import { configureShortcut } from "../Utils/utils";

// Stores whose games SkullKey can move between drives (Xbox moves itself).
const MOVABLE = ["GOGActions", "AmazonActions", "EpicActions", "PortsActions", "DisksActions"];

interface Platform { ActionId: string; Title: string; Category: string; enabled: boolean }
interface Installed { platform: Platform; setName: string; games: { name: string; shortname: string; steamClientID: string }[] }

async function storeSetName(serverAPI: ServerAPI): Promise<string | null> {
    const init = await executeAction<ExecuteArgs, ActionSet>(serverAPI, "MainMenu", "SkullKeyInit", { inputData: "" });
    return (init?.Content as ActionSet)?.SetName ?? null;
}

const Group: VFC<{ title: string; color: string; children?: any }> = ({ title, color, children }) => (
    <div style={{ margin: "8px 0", padding: "10px 12px", borderRadius: 6, background: "rgba(255,255,255,0.04)",
                  borderLeft: `3px solid ${color}` }}>
        <div style={{ fontSize: 13, fontWeight: 700, textTransform: "uppercase", letterSpacing: ".5px", color, marginBottom: 6 }}>
            {title}
        </div>
        {children}
    </div>
);

export const InstalledGamesPage: VFC<{ serverAPI: ServerAPI }> = ({ serverAPI }) => {
    const [groups, setGroups] = useState<Installed[] | null>(null);

    const load = async () => {
        const res = await serverAPI.callPluginMethod<{}, Platform[]>("platforms_get", {});
        const platforms = (res.success && Array.isArray(res.result) ? res.result : [])
            .filter(p => p.enabled && p.Category === "games");
        const root = await storeSetName(serverAPI);
        const out: Installed[] = [];
        for (const platform of platforms) {
            try {
                if (!root) break;
                const set = await executeAction<ExecuteArgs, ActionSet>(serverAPI, root, platform.ActionId, {});
                const setName = (set?.Content as ActionSet)?.SetName;
                if (!setName) continue;
                const content = await executeAction<ExecuteGetContentArgs, ContentResult<ContentType>>(
                    serverAPI, setName, "GetContent", { filter: "", installed: "true", limited: "false" });
                const games = ((content?.Content as GameDataList)?.Games ?? [])
                    .filter((g: any) => g.SteamClientID)
                    .map((g: any) => ({ name: g.Name, shortname: g.ShortName, steamClientID: String(g.SteamClientID) }));
                if (games.length) out.push({ platform, setName, games });
            } catch (e) { /* one store failing never hides the others */ }
        }
        setGroups(out);
    };
    useEffect(() => { load(); }, []);

    const move = async (setName: string, game: { shortname: string; steamClientID: string }) => {
        const drive = await pickInstallDrive(serverAPI);
        if (drive === null) return;
        notify({ title: "SkullKey", body: t("inst_moving") });
        if (setName === "XboxActions") {
            await executeAction<ExecuteArgs, any>(serverAPI, setName, "Move", { shortname: game.shortname, drive } as any);
            return;
        }
        const r = await serverAPI.callPluginMethod<any, any>("move_game", { actionSet: setName, shortname: game.shortname, drive });
        if (!r.success || !r.result?.ok) {
            notify({ title: "SkullKey", body: t("inst_move_failed", { error: (r.success && r.result?.error) || "?" }) });
            return;
        }
        // The game's files changed place: rebuild its Steam shortcut from the
        // store's own launch options.
        const id = parseInt(game.steamClientID);
        const res = await executeAction<any, any>(serverAPI, setName, "Install",
            { shortname: game.shortname, steamClientID: game.steamClientID });
        if (id && res?.Type === "LaunchOptions") configureShortcut(id, res.Content);
        notify({ title: "SkullKey", body: t("inst_moved") });
        load();
    };

    if (groups === null) return <div style={{ padding: 12, opacity: 0.7 }}>{t("inst_loading")}</div>;
    if (!groups.length) return <div style={{ padding: 12, opacity: 0.7 }}>{t("inst_none")}</div>;
    return (
        <div style={{ padding: "0 8px" }}>
            {groups.map(({ platform, setName, games }) => {
                const theme = storeTheme(platform.Title);
                const canMove = setName === "XboxActions" || MOVABLE.includes(setName);
                return (
                    <Group key={platform.ActionId} title={tabLabel(platform.Title)} color={theme.color}>
                        {games.map(game => (
                            <Focusable key={game.shortname} flow-children="horizontal"
                                style={{ display: "flex", alignItems: "center", gap: 8, padding: "3px 0" }}>
                                <span style={{ flex: 1, fontSize: 13 }}>{game.name}</span>
                                {canMove && (
                                    <DialogButton style={{ minWidth: 0, width: "auto", padding: "0 12px" }}
                                        onClick={() => move(setName, game)}>{t("inst_move")}</DialogButton>
                                )}
                                <DialogButton style={{ minWidth: 0, width: "auto", padding: "0 12px" }}
                                    onClick={() => {
                                        const modal = showModal(<GameDetailsItem serverAPI={serverAPI} shortname={game.shortname}
                                            initActionSet={setName} closeModal={() => { modal.Close(); load(); }} />);
                                    }}>{t("inst_manage")}</DialogButton>
                            </Focusable>
                        ))}
                    </Group>
                );
            })}
        </div>
    );
};

export const PlatformsPage: VFC<{ serverAPI: ServerAPI }> = ({ serverAPI }) => {
    const [platforms, setPlatforms] = useState<Platform[]>([]);
    useEffect(() => {
        serverAPI.callPluginMethod<{}, Platform[]>("platforms_get", {})
            .then(r => r.success && Array.isArray(r.result) && setPlatforms(r.result));
    }, []);
    const toggle = async (p: Platform, enabled: boolean) => {
        await serverAPI.callPluginMethod("platforms_set", { actionId: p.ActionId, enabled });
        setPlatforms(list => list.map(x => x.ActionId === p.ActionId ? { ...x, enabled } : x));
    };
    return (
        <div style={{ padding: "0 8px" }}>
            <div style={{ fontSize: 12, opacity: 0.7, margin: "6px 0" }}>{t("plat_desc")}</div>
            {(["games", "media"] as const).map(cat => (
                <Group key={cat} title={t(cat === "games" ? "cat_games" : "cat_media")} color={cat === "games" ? "#4caf50" : "#00bcd4"}>
                    {platforms.filter(p => p.Category === cat).map(p => (
                        <ToggleField key={p.ActionId} label={tabLabel(p.Title)} checked={p.enabled}
                            onChange={(v: boolean) => toggle(p, v)} />
                    ))}
                </Group>
            ))}
        </div>
    );
};
