import { ConfirmModal, DialogButton, DialogLabel, Navigation, ServerAPI, showModal } from "decky-frontend-lib";
import { ReactElement, VFC, useEffect, useState } from "react";
import {
    ActionSet, ContentError, ContentResult, ContentType,
    ExecuteArgs, ExecuteLoginArgs, GetSettingArgs, LaunchOptions, LoginStatus,
    SaveSettingsArgs, SettingsData
} from "../Types/Types";
import Logger from "../Utils/logger";
import { executeAction } from "../Utils/executeAction";
import { ErrorDisplay } from "./ErrorDisplay";
import { gameIDFromAppID } from "../Utils/utils";
import { ActionCard, storeTheme } from "./Styled";
import { t } from "../i18n";

// ── Connexion dans le navigateur de Steam (SkullKey #4) ─────────────────────
// SteamOS d'origine n'a pas GTK/WebKit pour Python : la fenêtre de connexion ne
// peut pas s'ouvrir. On ouvre alors la page du magasin dans le navigateur de
// Steam ; le backend y lit le code (CDP) et termine la connexion. Le suivi vit
// au niveau du MODULE : ouvrir le navigateur démonte cette page.
let browserPoll: ReturnType<typeof setInterval> | null = null;
let browserLoginError = "";

const startBrowserLogin = async (serverAPI: ServerAPI, actionSet: string, route: string) => {
    const r = await serverAPI.callPluginMethod<{ actionSet: string }, any>(
        "browser_login_start", { actionSet });
    const res = r.success ? r.result : null;
    if (!res?.ok || !res?.url) {
        browserLoginError = res?.error || "browser login failed";
        return false;
    }
    browserLoginError = "";
    Navigation.NavigateToExternalWeb(res.url);
    if (browserPoll) clearInterval(browserPoll);
    const started = Date.now();
    browserPoll = setInterval(async () => {
        const st = await serverAPI.callPluginMethod<{}, any>("browser_login_status", {});
        const status = st.success ? st.result?.status : null;
        if (status === "done" || status === "error" || Date.now() - started > 600000) {
            if (browserPoll) clearInterval(browserPoll);
            browserPoll = null;
            if (status !== "done") {
                browserLoginError = st.result?.message || "timeout";
                serverAPI.callPluginMethod("browser_login_cancel", {}).catch(() => {});
            }
            // Referme le navigateur : retour DIRECT sur la page du magasin, qui
            // se recharge et affiche le nouvel état de connexion. Pas
            // NavigateBack : dans le navigateur il recule dans SON historique
            // (Epic = 3 pages) au lieu de le quitter (mesuré 04/10).
            Navigation.Navigate(route);
        }
    }, 1500);
    return true;
};


export const LoginContent: VFC<{ serverAPI: ServerAPI; initActionSet: string; initAction: string; }> = ({ serverAPI, initActionSet, initAction }) => {
    const logger = new Logger("LoginContent");
    const [content, setContent] = useState<ContentResult<ContentType>>({ Type: "Empty", Content: {} });
    const [actionSetName, setActionSetName] = useState<string>("");
    const [LoggedIn, setLoggedIn] = useState<string>("false");
    const [SteamClientId, setSteamClientId] = useState<string>("");
    // Magasins qui installent un client dans un préfixe (Ubisoft) : bouton
    // « Supprimer » séparé de la déconnexion (le préfixe contient les jeux).
    const [removeInfo, setRemoveInfo] = useState<any>(null);
    const originRoute = location.pathname.replace('/routes', '');
    useEffect(() => {
        if (actionSetName !== "") {
            updateLoginStatus();
        }
    }, [LoggedIn, actionSetName]);
    const loadRemoveInfo = async () => {
        const r = await executeAction<ExecuteArgs, any>(serverAPI, actionSetName, "RemoveInfo", { inputData: "" });
        setRemoveInfo(r?.Type === "RemoveInfo" && (r.Content as any)?.Exists ? r.Content : null);
    };
    const askRemoveClient = () => {
        const games: string[] = removeInfo?.Games || [];
        showModal(<ConfirmModal strTitle={t("remove_client_title")} bDestructiveWarning
            strDescription={t("remove_client_desc", { size: removeInfo?.Size || "?" })
                + (games.length ? "\n\n" + t("remove_client_games", { games: games.join(", ") }) : "")}
            strOKButtonText={t("remove_client_ok")}
            onOK={async () => {
                const r = await executeAction<ExecuteArgs, ContentType>(serverAPI, actionSetName, "RemoveClient", { inputData: "" });
                if (r) setContent(r);
                loadRemoveInfo();
            }} />);
    };
    const updateLoginStatus = async () => {
        logger.debug("Updating login status with actionSetName: ", actionSetName);
        const result = await executeAction<ExecuteArgs, ContentType>(serverAPI, actionSetName,
            "GetContent",
            {
                inputData: ""
            });
        if (result == null) {
            logger.error("Login status is null");
            return;
        }
        setContent(result);
        logger.debug("Login status: ", result);
        loadRemoveInfo();
    };
    const onLoginExit = (id) => {
        Navigation.CloseSideMenus();
        Navigation.Navigate(originRoute);
        setTimeout(() => {
            SteamClient.Apps.RemoveShortcut(id);
        }, 1000);
    };
    const createShortcut = async (launchOptions: LaunchOptions) => {
        logger.debug("Creating shortcut for login: ", launchOptions);
        const id = await SteamClient.Apps.AddShortcut("Login", launchOptions.Exe, "", "");
        logger.debug("Shortcut created for login: ", id);
        SteamClient.Apps.SetShortcutLaunchOptions(id, launchOptions.Options);
        SteamClient.Apps.SetShortcutName(id, launchOptions.Name);
        logger.debug("Saving shortcut for login: ", id);
        await executeAction<SaveSettingsArgs, ContentType>(serverAPI, actionSetName,
            "SaveSetting",
            {
                name: "LoginSteamClientId",
                value: id.toString()
            });
        logger.debug("Shortcut created for login: ", id);
        setSteamClientId(id.toString());
        return id;
    };
    const getSteamClientId = async (launchOptions: LaunchOptions) => {
        if (SteamClientId === "") {
            logger.debug("No Shortcut found, creating one...");
            return await createShortcut(launchOptions);
        }
        else {
            const id = parseInt(SteamClientId);
            logger.debug("Shortcut configured: ", id);
            const app = appStore.allApps.find(a =>  a.appid == id);
            if (app) {
                logger.debug("Shortcut found: ", id);
                return id;
            }
            else {
                logger.debug("Shortcut not found, creating one...");
                return await createShortcut(launchOptions);
            }

        }
    };
    const login = async () => {
        try {
            const need = await serverAPI.callPluginMethod<{}, boolean>("browser_login_needed", {});
            if (need.success && need.result) {
                if (!(await startBrowserLogin(serverAPI, actionSetName, originRoute))) {
                    setContent({ Type: "Error", Content: {
                        Message: t("browser_login_failed"), Data: browserLoginError,
                        ActionSet: actionSetName, ActionName: "Login" } as any });
                }
                return;
            }
            const launchOptionsResult = await executeAction<ExecuteArgs, LaunchOptions>(serverAPI, actionSetName,
                "LoginLaunchOptions", {});
            logger.debug("launchOptionsResult: ", launchOptionsResult);
            if (launchOptionsResult == null) {
                logger.error("launchOptionsResult is null");
                return;
            }
            const launchOptions = launchOptionsResult?.Content;
            if (launchOptions == null) {
                logger.error("LaunchOptions is null");
                return;
            }
            
            
            const id = await getSteamClientId(launchOptions);
            const gameId = gameIDFromAppID(id);

            await executeAction<ExecuteLoginArgs, ContentType>(serverAPI, actionSetName,
                "Login",
                {
                    appId: String(id),
                    gameId: String(gameId)
                },
                () => onLoginExit(id)
            );

            setContent(launchOptionsResult);            
            setLoggedIn("true");

        } catch (error) {
            logger.error("Login: ", error);
        }
    };
    
    const logout = async () => {
        try {
            setContent({ Type: "Empty", Content: {} });
            const data = await executeAction<ExecuteArgs, LoginStatus>(serverAPI, actionSetName,
                "Logout",
                {
                    inputData: ""
                });
            
            if (data == null) {
                logger.error("login status is null");
                return;
            }
            setLoggedIn("false");
            setContent(data);
        } catch (error) {
            logger.error("Logout: ", error);
        }
    };
    const onInit = async () => {
        try {
            logger.debug(`Initializing LoginContent with initActionSet: ${initActionSet} and initAction: ${initAction}`);
            const data = await executeAction<ExecuteArgs, ActionSet>(serverAPI, initActionSet,
                initAction,
                {
                    inputData: ""
                });
            logger.debug("init result: ", data);
            const result = data?.Content as ActionSet;
            
            const tmp = await executeAction<GetSettingArgs, SettingsData>(serverAPI, result.SetName,
                "GetSetting",
                {
                    name: "LoginSteamClientId",
                    inputData: ""
                });
            const settings = tmp?.Content as SettingsData;
            if (settings.value !== "") {
              setSteamClientId(settings.value);
            }
            setActionSetName(result.SetName);
            setLoggedIn("unknown");

        } catch (error) {
            logger.error("OnInit: ", error);
        }
    };
    useEffect(() => {
        onInit();
        // Retour du navigateur après une connexion ratée : on le dit.
        if (browserLoginError && !browserPoll) {
            const msg = browserLoginError;
            browserLoginError = "";
            setTimeout(() => setContent({ Type: "Error", Content: {
                Message: t("browser_login_failed"), Data: msg,
                ActionSet: initActionSet, ActionName: "Login" } as any }), 1500);
        }
    }, []);

    const theme = storeTheme(actionSetName || initActionSet);
    const StoreIcon = theme.icon;
    const labelStyle = { flex: 'auto', margin: '0', display: 'flex', alignItems: 'center', gap: '8px' };
    let innerElement: ReactElement = <></>;

    switch (content.Type) {
        case 'LoginStatus':
            const status = content.Content as LoginStatus;
            const isLoggedIn = status.LoggedIn;
            innerElement = (
                <>
                    <DialogLabel style={labelStyle as any}>
                        <StoreIcon size={14} style={{ color: theme.color, flexShrink: 0 }} />
                        <span style={{
                            width: 8, height: 8, borderRadius: 4, flexShrink: 0,
                            background: isLoggedIn ? '#4caf50' : '#f44336',
                            boxShadow: `0 0 6px ${isLoggedIn ? '#4caf50' : '#f44336'}`,
                        }} />
                        {isLoggedIn ? <>{t('connected')} <b>{status.Username}</b></> : t('not_connected')}
                    </DialogLabel>
                    <div style={{ width: 130 }}>
                        <ActionCard color={theme.color} active={!isLoggedIn} onClick={isLoggedIn ? logout : login}>
                            {isLoggedIn ? t('logout') : t('login')}
                        </ActionCard>
                    </div>
                    {removeInfo && (
                        <div style={{ width: 130 }}>
                            <ActionCard color="#c0392b" onClick={askRemoveClient}>
                                {t('remove_client')}
                            </ActionCard>
                        </div>
                    )}
                </>
            );
            break;
        case 'Empty':
            innerElement = <DialogLabel style={labelStyle as any}>{t('checking_status')}</DialogLabel>;
            break;
        case 'Error':
            innerElement = <ErrorDisplay error={content.Content as ContentError} />;
    }

    return (
        <div style={{
            display: "flex", minHeight: '40px', alignItems: 'center', gap: 10,
            padding: '6px 10px', borderRadius: 6,
            background: 'rgba(255,255,255,0.04)',
            borderLeft: `3px solid ${theme.color}`,
        }}>
            {innerElement}
        </div>
    );
};
