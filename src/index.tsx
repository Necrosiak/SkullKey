import {
  definePlugin,
  Navigation,
  ServerAPI,
  showModal,
  staticClasses,
  useParams
} from "decky-frontend-lib";
import { FaSkull } from "react-icons/fa";

import { notify } from "./Components/Styled";
import { Content } from "./ContentTabs";
import { About } from "./About";
import { MainMenuModal } from "./MainMenuModal";
import { clearClickableNotifications } from "./clickableNotify";
import { portUpdateNotice } from "./portUpdateNotice";
import { t } from "./i18n";
import { SkullKeyDownloads } from "./Components/DownloadsSection";
import { startQueueRunner } from "./Utils/downloadQueue";

// Store name shown in free-game notifications.
const FREE_STORES: Record<string, string> = { epic: "Epic Games", gog: "GOG", steam: "Steam", ubisoft: "Ubisoft",
  battlenet: "Battle.net", ea: "EA", amazon: "Prime Gaming", itch: "itch.io" };
const freeStoreLabel = (key: string) => FREE_STORES[key] || key;


// ── Auto-update: the frontend only REPORTS ───────────────────────────────────
// The backend installs (it may: the plugin directory is root-owned, but the
// files inside belong to us). It is the only side that cannot raise a
// notification — hence this relay.
//
// ⛔ Do NOT call `DeckyBackend.call('utilities/install_plugin', …)`: that is the
// Decky Store route. It unpacks, then reports the install to
// plugins.deckbrew.xyz, which does not know our plugins → 404 → the rest never
// runs: files written, plugin never reloaded, and an "update in progress" modal
// frozen across the Steam UI. Measured on 2026-09-13 on BC250-Toolkit.
const UPDATE_POLL_MS = 5000;
const UPDATE_POLL_TRIES = 36; // 3 minutes, enough for a cold Game Mode boot

async function reportFailedUpdate(serverApi: ServerAPI) {
  for (let i = 0; i < UPDATE_POLL_TRIES; i++) {
    let notice: any = null;
    try {
      const r = await serverApi.callPluginMethod<{}, any>("take_pending_update", {});
      notice = r?.success ? r.result : null;
    } catch {
      // Backend not reachable yet — not a failure, we come back.
    }
    if (notice?.version) {
      notify({
        title: "SkullKey",
        body: `Update ${notice.version} could not be installed automatically. `
            + "Install it from Decky → Developer → Install plugin from URL.",
        clickKey: `update-failed:${notice.version}`,
        onClick: () => {
          Navigation.CloseSideMenus();
          Navigation.Navigate("/about-skullkey");
        },
      });
      return;
    }
    await new Promise((r) => setTimeout(r, UPDATE_POLL_MS));
  }
}

//@ts-ignore
export default definePlugin((serverApi: ServerAPI) => {

  reportFailedUpdate(serverApi);
  let checkingPorts = false;
  let disposed = false;
  const checkPortUpdates = async () => {
    if (checkingPorts || disposed) return;
    checkingPorts = true;
    try {
      const reply = await serverApi.callPluginMethod<{}, any[]>("take_port_update_events", {});
      if (!disposed && reply.success && Array.isArray(reply.result)) {
        for (const event of reply.result) {
          if (!event || typeof event.name !== "string" || typeof event.version !== "string" || typeof event.success !== "boolean") continue;
          notify({
            title: "SkullKey — " + event.name,
            body: portUpdateNotice(event.success, event.version),
            clickKey: `port-update:${event.appid}:${event.version}:${event.success}`,
            onClick: () => {
              Navigation.CloseSideMenus();
              const id = Number(event.appid);
              Navigation.Navigate(id > 0 ? `/library/app/${id}` : "/about-skullkey");
            },
          });
        }
      }
    } catch (error) { console.debug("[SkullKey] port update poll", error); }
    finally { checkingPorts = false; }
  };
  checkPortUpdates();

  const stopQueue = startQueueRunner(serverApi);

  // SkullKey downloads at the top of Steam's Downloads page.
  const downloadsPatch = serverApi.routerHook.addPatch("/library/downloads", (route: any) => {
    const original = route.children;
    route.children = (
      <div style={{ display: "flex", flexDirection: "column", height: "100%" }}>
        <SkullKeyDownloads serverAPI={serverApi} />
        <div style={{ flex: 1, minHeight: 0, position: "relative" }}>{original}</div>
      </div>
    );
    return route;
  });
  const portsTimer = setInterval(checkPortUpdates, 30000);

  // Free games (Epic, GOG, Steam, Prime Gaming…): the backend fetches at most
  // every 6 h and only returns offers never announced before. Clicking opens
  // the claim page in Steam's browser — the player confirms it there.
  const checkFreeGames = async () => {
    try {
      const reply = await serverApi.callPluginMethod<{}, any[]>("free_games_events", {});
      if (!reply.success || !Array.isArray(reply.result)) return;
      for (const g of reply.result) {
        notify({
          title: t("free_notif_title", { store: freeStoreLabel(g.store) }),
          body: g.end ? t("free_notif_body_until", { game: g.title, date: g.end }) : t("free_notif_body", { game: g.title }),
          clickKey: `free-game:${g.id}`,
          onClick: () => { Navigation.CloseSideMenus(); Navigation.NavigateToExternalWeb(g.url); },
        });
      }
    } catch (error) { console.debug("[SkullKey] free games poll", error); }
  };
  const freeGamesFirst = setTimeout(checkFreeGames, 60000);
  const freeGamesTimer = setInterval(checkFreeGames, 30 * 60000);

  // One-shot migration of the pre-rename localStorage keys (js_* → sk_*).
  try {
    for (const key of Object.keys(localStorage)) {
      if (key.startsWith("js_")) {
        const target = "sk_" + key.slice(3);
        if (localStorage.getItem(target) === null) {
          localStorage.setItem(target, localStorage.getItem(key)!);
        }
        localStorage.removeItem(key);
      }
    }
  } catch (e) { }

  let l3Pressed = false;
  let r3Pressed = false;

  const unregister = SteamClient.Input.RegisterForControllerInputMessages(
    (e) => {
      if (Array.isArray(e)) {
        if (e[0]) {
          if (e[0].nA == 25) {
            l3Pressed = e[0].bS;
          }
          if (e[0].nA == 41) {
            r3Pressed = e[0].bS;
          }
        }
      }

      if (l3Pressed && r3Pressed && localStorage.getItem('sk_doubleStick') === 'true') {
        Navigation.CloseSideMenus();
        showModal(<MainMenuModal serverApi={serverApi} />);

      }
    })

  serverApi.routerHook.addRoute(
    "/skullkey-content/:initActionSet/:initAction/:category?",
    () => {
      const { initActionSet, initAction, category } = useParams<{ initActionSet: string; initAction: string; category?: string }>();
      return <Content key={initActionSet + "_" + initAction + "_" + (category ?? "")} serverAPI={serverApi} initActionSet={initActionSet} initAction={initAction} category={category} />;
    },
    {
      exact: true,
    }
  );
  serverApi.routerHook.addRoute(
    "/about-skullkey",
    () => {
      return <About serverAPI={serverApi} />
    },
    {
      exact: true,
    }
  );

  return {
    title: <div className={staticClasses.Title}>SkullKey</div>,
    content: <Content serverAPI={serverApi} initActionSet="init" initAction="InitActions" />,
    icon: <FaSkull />,
    onDismount() {
      disposed = true;
      clearInterval(portsTimer); serverApi.routerHook.removePatch("/library/downloads", downloadsPatch); stopQueue(); clearInterval(freeGamesTimer); clearTimeout(freeGamesFirst);
      clearClickableNotifications("skullkey");
      serverApi.routerHook.removeRoute("/skullkey-content/:initActionSet/:initAction/:category?");
      serverApi.routerHook.removeRoute("/about-skullkey");
      unregister.unregister();
    },
  };
});
