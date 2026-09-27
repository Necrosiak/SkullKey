import { LaunchOptions } from "../Types/Types";
import Logger from "./logger";

export enum AppRunStateChange {
    START,
    END,
    BOTH
}

export function gameIDFromAppID(appid: number) {
    let game = appStore.GetAppOverviewByAppID(appid);

    if (game) {
        return game.m_gameid;
    } else {
        return -1;
    }
};

export async function getAppDetails(appId: number | string) {
    const id = typeof appId === 'string' ? parseInt(appId) : appId
    await appDetailsStore.RequestAppDetails(id);
    return appDetailsStore.GetAppDetails(id);
}

export function runApp(appId: number, onAppClose?: () => void, onAppLaunch?: () => void) {
    const logger = new Logger('runApp');
    logger.debug(`Running appId: ${appId}`)
    if (onAppLaunch) {
        const { unregister } = registerForAppRunStateChange(appId, () => {
            onAppLaunch();
            unregister();
        }, AppRunStateChange.START);
    }
    if (onAppClose) {
        const { unregister } = registerForAppRunStateChange(appId, () => {
            // Add a delay due to UI not updating in time - this is a workaround for now
            setTimeout(() => {
                logger.debug(`App ${appId} closed running onAppClose callback`);
                onAppClose();
            }
                , 1000);
            unregister();
        }, AppRunStateChange.END);
    }
    let gid = gameIDFromAppID(appId);
    if (gid && gid !== -1) SteamClient.Apps.RunGame(gid as string, "", -1, 100);
}

export function registerForAppRunStateChange(appId: number, callback: () => void, stateChange: AppRunStateChange): { unregister: () => void; } {
    return SteamClient.GameSessions.RegisterForAppLifetimeNotifications((data: { unAppID: number; nInstanceID: number; bRunning: boolean; }) => {
        if (data.unAppID !== appId) return;
        switch (stateChange) {
            case AppRunStateChange.START:
                if (data.bRunning) callback();
                break;
            case AppRunStateChange.END:
                if (!data.bRunning) callback();
                break;
            case AppRunStateChange.BOTH:
                callback();
        }
    });
}

export function configureShortcut(id: number, launchOptions: LaunchOptions) {
    const logger = new Logger("configureShortcut");

    if (launchOptions) {
        logger.debug("launchOptions: ", launchOptions);
        SteamClient.Apps.SetAppLaunchOptions(id, launchOptions.Options);
        SteamClient.Apps.SetShortcutExe(id, launchOptions.Exe);
        SteamClient.Apps.SetShortcutStartDir(id, launchOptions.WorkingDir);

        if (launchOptions.Compatibility) {
            SteamClient.Apps.SpecifyCompatTool(id, launchOptions.CompatToolName ?? '');
        }
    }
}
// A store client that has to be visible in gamescope (Battle.net) must be
// started by Steam, from a shortcut. The backend describes that shortcut; it
// is created once and found again by its name, then run.
const SHORTCUT_APP_TYPE = 1073741824;

function findShortcutByName(name: string) {
    return appStore.allApps.find(a => a.app_type == SHORTCUT_APP_TYPE && a.display_name == name);
}

export async function runHelperShortcut(launchOptions: LaunchOptions): Promise<number> {
    const logger = new Logger('runHelperShortcut');
    let id = findShortcutByName(launchOptions.Name)?.appid;
    if (!id) {
        id = await SteamClient.Apps.AddShortcut(launchOptions.Name, launchOptions.Exe, launchOptions.WorkingDir, "");
        SteamClient.Apps.SetShortcutName(id, launchOptions.Name);
        logger.debug("created helper shortcut", id);
    }
    configureShortcut(id, launchOptions);
    // A fresh shortcut has no overview (hence no game id) for a moment.
    for (let i = 0; i < 20 && gameIDFromAppID(id) === -1; i++) {
        await new Promise(resolve => setTimeout(resolve, 250));
    }
    const gid = gameIDFromAppID(id);
    if (gid !== -1) SteamClient.Apps.RunGame(gid as string, "", -1, 100);
    return id;
}

// Bring an already running helper shortcut back to the foreground.
export function focusShortcut(name: string) {
    const app = findShortcutByName(name);
    if (!app) return;
    const gid = gameIDFromAppID(app.appid);
    if (gid !== -1) SteamClient.Apps.RunGame(gid as string, "", -1, 100);
}
