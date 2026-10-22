import { DialogButton, Focusable, Menu, MenuItem, Navigation, ServerAPI, Spinner, TextField, gamepadTabbedPageClasses, showContextMenu, showModal } from "decky-frontend-lib";
import { openDiskAdd } from "./DiskAddModal";
import { ContentResult, ContentType, ExecuteArgs, GameData, GameDataList, MenuAction, ScriptActions } from "../Types/Types";
import { Dispatch, SetStateAction, VFC, memo, useEffect, useState } from "react";
import GameGridItem from './GameGridItem';
import { GameDetailsItem } from './GameDetailsItem';
import Logger from "../Utils/logger";
import { FaSlidersH, FaCog, FaRegCheckCircle } from 'react-icons/fa';
import { LoginContent } from './LoginContent';
import { executeAction } from '../Utils/executeAction';
import { ConfEditor } from '../ConfEditor';
import { FaStore } from "react-icons/fa6";
import { IconBtn, storeTheme } from './Styled';
import { t } from '../i18n';

export const contentTabsContainerClass = 'content-tabs-container';
export const gridContentContainerClass = 'grid-content-container';

interface GridContentArgs {
    filter?: string;
    installed?: boolean;
    limited?: boolean;
    access?: string;
}

interface GridContentCache {
    filter: string;
    installed: boolean;
}

interface GridContentProps {
    content: GameDataList;
    serverAPI: ServerAPI;
    initActionSet: string;
    refreshContent: (actionArgs: GridContentArgs, onFinish?: () => void) => void;
    argsCache: GridContentCache;
    setArgsCache: Dispatch<SetStateAction<GridContentCache>>;
}

export const GridContent: VFC<GridContentProps> = ({ content, serverAPI, initActionSet, refreshContent, argsCache, setArgsCache }) => {
    const logger = new Logger('ContentGrid');
    const [isLimited, setIsLimited] = useState(false);
    const [isLimitedLoading, setIsLimitedLoading] = useState(false);
    const [installedFilterLoading, setInstalledLoading] = useState(false);
    const [scriptActions, setScriptActions] = useState<MenuAction[] | null>();
    const [filter, setFilter] = useState(argsCache.filter);
    // L'icône des réglages seulement si le magasin a une page de réglages :
    // Ubisoft, Battle.net, Minecraft… n'en ont pas, et l'appeler ouvrait une
    // fenêtre « Action not found » (SkullKey #4).
    const [hasTabConfig, setHasTabConfig] = useState(false);
    const [accessFilter, setAccessFilter] = useState<string>("");
    // A sign-in that finished on its own page (Xbox) changes the library.
    useEffect(() => {
        const onDone = () => refreshContent({ ...argsCache, limited: isLimited });
        window.addEventListener("skullkey-login-done", onDone);
        return () => window.removeEventListener("skullkey-login-done", onDone);
    }, [argsCache, isLimited]);
    useEffect(() => {
        serverAPI.callPluginMethod<{ actionSet: string; actionName: string }, boolean>(
            "has_action", { actionSet: initActionSet, actionName: "GetTabConfigActions" })
            .then((r) => setHasTabConfig(!!(r.success && r.result))).catch(() => setHasTabConfig(false));
    }, [initActionSet]);

    useEffect(() => {
        (async () => {
            try {
                const actionRes = await executeAction<ExecuteArgs, ScriptActions>(serverAPI, initActionSet, "GetScriptActions", {});
                logger.debug('Get sscript actions result', actionRes);
                if (!actionRes) {
                    return;
                }
                const scriptActions = actionRes.Content;
                setScriptActions(scriptActions.Actions);
            }
            catch (e) {
                logger.error(e);
            }
        })();
    }, []);

    const actionsMenu = (e: any) => {
        showContextMenu(
            <Menu label={t("menu_actions")} cancelText={t("menu_cancel")} onCancel={() => { }}>
                {scriptActions?.map((action) =>
                    <MenuItem
                        onSelected={async () => {
                            const args = {
                                shortname: "",
                                steamClientID: "",
                                startDir: "",
                                compatToolName: "",
                                inputData: "",
                                gameId: "",
                                appId: ""
                            };
                            const result = await executeAction<ExecuteArgs, ContentResult<ContentType>>(serverAPI, initActionSet, action.ActionId, args);
                            if (result?.Type == "RefreshContent") {
                                refreshContent({ ...argsCache, limited: isLimited });
                            }
                            logger.debug("runScript result", result);
                        }}
                    >
                        {action.Title}
                    </MenuItem>
                )}
            </Menu>,
            e.currentTarget ?? window
        );
    };

    const updateCache: <Param extends keyof GridContentArgs>(param: Param, value: GridContentArgs[Param], onFinish?: () => void) => void =
        (param, value, onFinish) => {
            const newCache = { ...argsCache, [param]: value };
            refreshContent({ ...newCache, limited: isLimited }, () => {
                setArgsCache(newCache);
                onFinish?.();
            });
        };

    return (
        <Focusable
            className={gridContentContainerClass}
            onSecondaryButton={() => {
                setInstalledLoading(true);
                updateCache('installed', !argsCache.installed, () => setInstalledLoading(false));
            }}
            onOptionsButton={() => {
                setIsLimitedLoading(true);
                refreshContent({ ...argsCache, limited: !isLimited }, () => {
                    setIsLimited(!isLimited);
                    setIsLimitedLoading(false);
                });
            }}
            onSecondaryActionDescription={
                <div style={{ display: 'flex', gap: '4px' }}>
                    <text>Toggle Installed</text>
                    {argsCache.installed && <FaRegCheckCircle style={{ alignSelf: 'center' }} size='14px' />}
                    {installedFilterLoading && <Spinner style={{ width: '20px' }} />}
                </div>
            }
            onOptionsActionDescription={
                <div style={{ display: 'flex', gap: '4px' }}>
                    <text>{isLimited ? t('show_all') : t('limit_results')}</text>
                    {isLimitedLoading && <Spinner style={{ width: '20px' }} />}
                </div>
            }
        >
            <style>{`
                .${contentTabsContainerClass} .${gamepadTabbedPageClasses.TabContentsScroll} {
                    scroll-padding-top: calc( var(--basicui-header-height) + 140px ) !important;
                    scroll-padding-bottom: 80px;
                }
                .${contentTabsContainerClass} .${gamepadTabbedPageClasses.TabContents} .${gridContentContainerClass} {
                    padding-top: 15px;
                }
            `}</style>
            <Focusable style={{ display: "flex", gap: '15px' }}>
                <div style={{ width: '100%' }}>
                    <TextField
                        placeholder={t("search")}
                        value={filter}
                        onChange={(e) => {
                            updateCache('filter', e.target.value);
                            setFilter(e.target.value);
                        }}
                    />
                </div>
                {initActionSet === "DisksActions" && (
                    <DialogButton style={{ minWidth: 0, width: "auto", padding: "0 14px", whiteSpace: "nowrap" }}
                        onClick={() => openDiskAdd(serverAPI, () => refreshContent && refreshContent())}>
                        {t("disks_add_button")}
                    </DialogButton>
                )}
                <IconBtn color={storeTheme(initActionSet).color} onClick={actionsMenu} disabled={!scriptActions}>
                    <FaSlidersH style={{ verticalAlign: 'middle' }} />
                </IconBtn>
                {hasTabConfig && <IconBtn color={storeTheme(initActionSet).color} onClick={() => showModal(
                    <ConfEditor
                        serverAPI={serverAPI}
                        initActionSet={initActionSet}
                        initAction="GetTabConfigActions"
                        contentId="0"
                        refreshParent={() => refreshContent({ ...argsCache, limited: isLimited })}
                    />
                )}>
                    <FaCog style={{ verticalAlign: 'middle' }} />
                </IconBtn>}
                {content.storeURL &&
                    <IconBtn color={storeTheme(initActionSet).color} onClick={() => {
                        if (content.storeURL)
                            Navigation.NavigateToExternalWeb(content.storeURL);
                    }}>
                        <FaStore />
                    </IconBtn>}
            </Focusable>
            {content.NeedsLogin === "true" && (
                <div style={{ paddingTop: '15px' }}>
                    <LoginContent serverAPI={serverAPI} initActionSet={initActionSet} initAction="GetLoginActions" />
                </div>
            )}
            {initActionSet === "XboxActions" && (
                // Steam marks the controller-focused button with .gpfocus; our inline
                // colours would hide its highlight, so draw a clear ring instead.
                <style>{`.sk-pill.gpfocus { outline: 2px solid #fff !important; outline-offset: 2px;
                    filter: brightness(1.35); transform: scale(1.06); }`}</style>
            )}
            {initActionSet === "XboxActions" && (
                <Focusable flow-children="horizontal" style={{ display: "flex", gap: 8, paddingTop: 12, flexWrap: "wrap" }}>
                    {(["", "owned", "gamepass", "free", "installed"] as const).map(key => {
                        const active = accessFilter === key;
                        const color = storeTheme(initActionSet).color;
                        return (
                            <DialogButton key={key || "all"} className="sk-pill"
                                style={{
                                    minWidth: 0, width: "auto", height: 32, padding: "0 18px", whiteSpace: "nowrap",
                                    borderRadius: 16, fontSize: 13, fontWeight: 600, letterSpacing: ".3px",
                                    lineHeight: "32px",
                                    background: active ? color : "rgba(255,255,255,0.06)",
                                    color: active ? "#fff" : "rgba(255,255,255,0.75)",
                                    border: active ? `1px solid ${color}` : "1px solid rgba(255,255,255,0.12)",
                                    boxShadow: active ? `0 0 10px ${color}66` : "none",
                                }}
                                onClick={() => {
                                    setAccessFilter(key);
                                    refreshContent({ ...argsCache, limited: isLimited, access: key });
                                }}>
                                {t(key ? `xbox_filter_${key}` : "xbox_filter_all")}
                            </DialogButton>
                        );
                    })}
                </Focusable>
            )}
            {argsCache.installed && (
                <div style={{ margin: '8px', display: 'flex', justifyContent: 'center', alignItems: 'center', gap: '5px' }}>
                    <div style={{ backgroundColor: storeTheme(initActionSet).color + '66', flex: 'auto', height: '1px' }} />
                    <div style={{ color: storeTheme(initActionSet).color, fontSize: '12px', textTransform: 'uppercase', fontWeight: 700 }}>
                        Installed
                    </div>
                    <div style={{ backgroundColor: storeTheme(initActionSet).color + '66', flex: 'auto', height: '1px' }} />
                </div>
            )}
            {content.Games?.length === 0 && (
                <div style={{ textAlign: 'center', padding: '15px' }}>
                   
                    {argsCache.filter !== "" && (
                        <div>
                            No games match the filter: {argsCache.filter}. Clear the search bar.
                        </div>
                    )}
                    {argsCache.installed && (
                        <div>
                            No installed games. Push X to toggle installed games off.
                        </div>
                    )}
                </div>   
            )}
            <GridItems
                serverAPI={serverAPI}
                games={content.Games ?? []}
                initActionSet={initActionSet}
            />
        </Focusable>
    );
};

interface GridItemsProperties {
    games: GameData[];
    serverAPI: ServerAPI;
    initActionSet: string;
}

const GridItems: VFC<GridItemsProperties> = memo(({ serverAPI, games, initActionSet }) => {
    const logger = new Logger("GridContainer");

    const imgAreaWidth = '120px';
    const imgAreaHeight = '165px';

    return (
        <>
            <Focusable
                style={{
                    display: "grid",
                    justifyContent: "space-between",
                    gridGap: "16px 12px",
                    gridTemplateColumns: `repeat(auto-fill, ${imgAreaWidth})`,
                    marginTop: '15px'
                }}
                //@ts-ignore
                navEntryPreferPosition={0} // always enter the grid on its first game (top left)
            >
                {games.map((game: GameData) => (
                    <GameGridItem
                        gameData={game}
                        imgAreaWidth={imgAreaWidth}
                        imgAreaHeight={imgAreaHeight}
                        onClick={() => {
                            logger.debug("onClick game: ", game);
                            // logger.debug("setActiveGame", game.ShortName);
                            // setActiveGame(game.ShortName);
                            const modal = showModal(
                                <GameDetailsItem
                                    serverAPI={serverAPI}
                                    shortname={game.ShortName}
                                    initActionSet={initActionSet}
                                    closeModal={() => modal.Close()}
                                />
                            );
                        }}
                    />
                ))}
            </Focusable>
        </>
    );
});
