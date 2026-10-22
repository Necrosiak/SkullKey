// Settings pages: installed games of every platform, and switching platforms
// on or off. Both reuse the store plumbing: the store's own GetContent with
// installed=true, and the game page every tab already opens.
import { ConfirmModal, DialogButton as SteamButton, Focusable, Navigation, ServerAPI, TextField, ToggleField, showModal } from "decky-frontend-lib";
import { VFC, useEffect, useState } from "react";
import { ActionSet, ExecuteArgs, ExecuteGetContentArgs, ContentResult, ContentType, GameDataList } from "../Types/Types";
import { executeAction } from "../Utils/executeAction";
import { GameDetailsItem } from "./GameDetailsItem";
import { pickInstallDrive } from "./DrivePicker";
import { notify, storeTheme } from "./Styled";
import { t, tabLabel } from "../i18n";
import { configureShortcut } from "../Utils/utils";

// Stores whose games SkullKey can move between drives (Xbox moves itself).
// Compact pill buttons, same look as the Xbox filters.
const PILL = { minWidth: 0, width: "auto", height: 28, lineHeight: "28px", padding: "0 16px", borderRadius: 14,
               fontSize: 12, fontWeight: 600, letterSpacing: ".3px", background: "rgba(255,255,255,0.06)",
               color: "rgba(255,255,255,0.8)", border: "1px solid rgba(255,255,255,0.12)" };
// DialogButton drops className, so the focus ring is driven from focus events.
const DialogButton: VFC<any> = ({ style, ...props }) => {
    const [focus, setFocus] = useState(false);
    return <SteamButton {...props} onGamepadFocus={() => setFocus(true)} onGamepadBlur={() => setFocus(false)}
        style={focus ? { ...style, outline: "2px solid #fff", outlineOffset: 2, filter: "brightness(1.3)" } : style} />;
};

const MOVABLE = ["GOGActions", "AmazonActions", "EpicActions", "PortsActions", "DisksActions"];

interface Platform { ActionId: string; Title: string; Category: string; enabled: boolean }
interface Installed { platform: Platform; setName: string; games: { name: string; shortname: string; steamClientID: string }[] }

async function storeSetName(serverAPI: ServerAPI): Promise<string | null> {
    const init = await executeAction<ExecuteArgs, ActionSet>(serverAPI, "MainMenu", "SkullKeyInit", { inputData: "" });
    return (init?.Content as ActionSet)?.SetName ?? null;
}

const Group: VFC<{ title: string; color: string; icon?: any; children?: any }> = ({ title, color, icon: Icon, children }) => (
    <div style={{ margin: "8px 0", padding: "10px 12px", borderRadius: 6, background: "rgba(255,255,255,0.04)",
                  borderLeft: `3px solid ${color}` }}>
        <div style={{ fontSize: 13, fontWeight: 700, textTransform: "uppercase", letterSpacing: ".5px", color, marginBottom: 6,
                      display: "flex", alignItems: "center", gap: 8 }}>
            {Icon && <Icon size={16} />}{title}
        </div>
        {children}
    </div>
);

export const InstalledGamesPage: VFC<{ serverAPI: ServerAPI }> = ({ serverAPI }) => {
    const [groups, setGroups] = useState<Installed[] | null>(null);
    // Size on disk per game, filled in one by one after the list shows.
    const [sizes, setSizes] = useState<Record<string, number>>({});
    // After a delete the focused row disappears and Steam would send the focus
    // back to the left menu: remount the list with the focus on the Delete
    // button of the next game (or the previous one).
    const [focusKey, setFocusKey] = useState<string | null>(null);
    const [listVersion, setListVersion] = useState(0);

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
        for (const g of out) {
            for (const game of g.games) {
                serverAPI.callPluginMethod<any, number>("game_size", { actionSet: g.setName, shortname: game.shortname })
                    .then(r => r.success && typeof r.result === "number" && r.result > 0 &&
                        setSizes(s => ({ ...s, [g.setName + ":" + game.shortname]: r.result })));
            }
        }
    };
    useEffect(() => { load(); }, []);

    const remove = (setName: string, game: { name: string; shortname: string; steamClientID: string }) => {
        showModal(
            <ConfirmModal strTitle={t("inst_delete_title", { game: game.name })} strDescription={t("inst_delete_desc")}
                strOKButtonText={t("inst_delete")} bDestructiveWarning
                onOK={async () => {
                    const flat = (groups || []).flatMap(g => g.games.map(x => g.setName + ":" + x.shortname));
                    const i = flat.indexOf(setName + ":" + game.shortname);
                    setFocusKey(flat[i + 1] ?? flat[i - 1] ?? null);
                    notify({ title: "SkullKey", body: t("inst_deleting", { game: game.name }) });
                    try {
                        // Discs & Installers: keep the saves, like the safe choice on the game page.
                        await executeAction<ExecuteArgs, any>(serverAPI, setName, "Uninstall",
                            { shortname: game.shortname, ...(setName === "DisksActions" ? { keep: "keep" } : {}) } as any);
                        const id = parseInt(game.steamClientID);
                        if (id) SteamClient.Apps.RemoveShortcut(id);
                        notify({ title: "SkullKey", body: t("inst_deleted", { game: game.name }) });
                    } catch (e) {
                        notify({ title: "SkullKey", body: t("inst_delete_failed", { game: game.name }) });
                    }
                    await load();
                    setListVersion(v => v + 1);
                }} />
        );
    };

    const fmtSize = (b: number) => b >= 1 << 30 ? `${(b / (1 << 30)).toFixed(1)} GB` : `${Math.max(1, Math.round(b / (1 << 20)))} MB`;

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
        <div key={listVersion} style={{ padding: "0 8px" }}>
            {groups.map(({ platform, setName, games }) => {
                const theme = storeTheme(platform.Title);
                const canMove = setName === "XboxActions" || MOVABLE.includes(setName);
                return (
                    <Group key={platform.ActionId} title={tabLabel(platform.Title)} color={theme.color} icon={theme.icon}>
                        {games.map(game => (
                            <Focusable key={game.shortname} flow-children="horizontal"
                                // Up/down keeps the same column (Delete -> Delete) instead of
                                // landing on the first button of the next row.
                                navEntryPreferPosition={2}
                                style={{ display: "flex", alignItems: "center", gap: 8, padding: "3px 0" }}>
                                <span style={{ flex: 1, fontSize: 13 }}>{game.name}</span>
                                <span style={{ fontSize: 12, opacity: 0.6, minWidth: 64, textAlign: "right" }}>
                                    {sizes[setName + ":" + game.shortname] ? fmtSize(sizes[setName + ":" + game.shortname]) : ""}
                                </span>
                                {canMove && (
                                    <DialogButton style={PILL}
                                        onClick={() => move(setName, game)}>{t("inst_move")}</DialogButton>
                                )}
                                <DialogButton style={PILL}
                                    onClick={() => {
                                        const modal = showModal(<GameDetailsItem serverAPI={serverAPI} shortname={game.shortname}
                                            initActionSet={setName} closeModal={() => { modal.Close(); load(); }} />);
                                    }}>{t("inst_manage")}</DialogButton>
                                <DialogButton style={{ ...PILL, color: "#ff8a80", border: "1px solid rgba(255,82,82,0.35)" }}
                                    autoFocus={focusKey === setName + ":" + game.shortname}
                                    onClick={() => remove(setName, game)}>{t("inst_delete")}</DialogButton>
                            </Focusable>
                        ))}
                    </Group>
                );
            })}
        </div>
    );
};

// Platform name with its store icon, tinted with the store colour.
const PlatformLabel: VFC<{ title: string }> = ({ title }) => {
    const { color, icon: Icon } = storeTheme(title);
    return (
        <span style={{ display: "inline-flex", alignItems: "center", gap: 12 }}>
            <span style={{ width: 22, display: "inline-flex", justifyContent: "center", color }}>
                {Icon && <Icon size={20} />}
            </span>
            {tabLabel(title)}
        </span>
    );
};

// Optional SteamGridDB key: logos for every game (Downloads page) when the
// store and the Steam page have none. Stays on this machine.
const SgdbKey: VFC<{ serverAPI: ServerAPI }> = ({ serverAPI }) => {
    const [has, setHas] = useState<boolean | null>(null);
    const [value, setValue] = useState("");
    const [msg, setMsg] = useState("");
    useEffect(() => { serverAPI.callPluginMethod<{}, boolean>("sgdb_has_key", {}).then(r => r.success && setHas(!!r.result)); }, []);
    const save = async () => {
        setMsg(t("sgdb_checking"));
        const r = await serverAPI.callPluginMethod<{ key: string }, boolean>("sgdb_set_key", { key: value });
        const ok = r.success && !!r.result;
        setMsg(ok ? t("sgdb_saved") : t("sgdb_invalid"));
        if (ok) { setHas(true); setValue(""); }
    };
    return (
        <Group title={t("sgdb_title")} color="#5b8def">
            <div style={{ fontSize: 12, opacity: 0.75, margin: "2px 0 8px" }}>{t("sgdb_desc")}</div>
            <div style={{ fontSize: 13, marginBottom: 6 }}>{has ? "\u2713 " + t("sgdb_has") : t("sgdb_none")}</div>
            <Focusable flow-children="horizontal" style={{ display: "flex", gap: 8, alignItems: "center" }}>
                <div style={{ flex: 1 }}>
                    <TextField bIsPassword value={value} onChange={(e: any) => setValue(e.target.value)} />
                </div>
                <DialogButton style={PILL} onClick={save}>{t("sgdb_save")}</DialogButton>
            </Focusable>
            {msg && <div style={{ fontSize: 12, marginTop: 6, opacity: 0.85 }}>{msg}</div>}
        </Group>
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
                        <ToggleField key={p.ActionId} label={<PlatformLabel title={p.Title} />} checked={p.enabled}
                            onChange={(v: boolean) => toggle(p, v)} />
                    ))}
                </Group>
            ))}
            <SgdbKey serverAPI={serverAPI} />
        </div>
    );
};

interface FreeOffer { id: string; store: string; title: string; now: boolean; start: string; end: string; url: string }
interface FreeList { offers: FreeOffer[]; enabled: string[]; stores: { key: string; label: string }[] }

// Free games to claim, and which stores to be notified for. Claim opens the
// store page in Steam's browser: the player confirms the (free) order there.
export const FreeGamesPage: VFC<{ serverAPI: ServerAPI }> = ({ serverAPI }) => {
    const [data, setData] = useState<FreeList | null>(null);
    const load = (force = false) => serverAPI.callPluginMethod<any, FreeList>("free_games_list", { force })
        .then(r => r.success && setData(r.result));
    useEffect(() => { load(); }, []);
    const toggle = async (key: string, on: boolean) => {
        await serverAPI.callPluginMethod("free_games_set", { store: key, enabled: on });
        load(true);
    };
    if (data === null) return <div style={{ padding: 12, opacity: 0.7 }}>{t("inst_loading")}</div>;
    const label = (k: string) => data.stores.find(s => s.key === k)?.label || k;
    const offers = (now: boolean) => data.offers.filter(o => o.now === now && data.enabled.includes(o.store));
    const list = (items: FreeOffer[]) => items.map(o => (
        <Focusable key={o.id} flow-children="horizontal" style={{ display: "flex", alignItems: "center", gap: 8, padding: "3px 0" }}>
            <span style={{ width: 22, display: "inline-flex", justifyContent: "center", color: storeTheme(o.store).color }}>
                {(() => { const I = storeTheme(o.store).icon; return I ? <I size={16} /> : null; })()}
            </span>
            <span style={{ flex: 1, fontSize: 13 }}>
                {o.title}
                <span style={{ opacity: 0.6, marginLeft: 8, fontSize: 11 }}>
                    {label(o.store)}{o.now ? (o.end ? " · " + t("free_until", { date: o.end }) : "") : " · " + t("free_from", { date: o.start })}
                </span>
            </span>
            {o.now && (
                <DialogButton style={PILL} onClick={() => { Navigation.CloseSideMenus(); Navigation.NavigateToExternalWeb(o.url); }}>
                    {t("free_claim")}
                </DialogButton>
            )}
        </Focusable>
    ));
    const now = offers(true), soon = offers(false);
    return (
        <div style={{ padding: "0 8px" }}>
            <div style={{ fontSize: 12, opacity: 0.7, margin: "6px 0" }}>{t("free_desc")}</div>
            <Group title={t("free_now")} color="#4caf50">
                {now.length ? list(now) : <div style={{ fontSize: 13, opacity: 0.7 }}>{t("free_none")}</div>}
                <Focusable style={{ display: "flex", justifyContent: "flex-end", paddingTop: 6 }}>
                    <DialogButton style={PILL} onClick={() => load(true)}>{t("free_refresh")}</DialogButton>
                </Focusable>
            </Group>
            {!!soon.length && <Group title={t("free_soon")} color="#ff9800">{list(soon)}</Group>}
            <Group title={t("free_notify_for")} color="#00bcd4">
                {data.stores.map(s => (
                    <ToggleField key={s.key} label={<PlatformLabel title={s.label} />}
                        checked={data.enabled.includes(s.key)} onChange={(v: boolean) => toggle(s.key, v)} />
                ))}
            </Group>
        </div>
    );
};
