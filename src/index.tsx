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
      });
      return;
    }
    await new Promise((r) => setTimeout(r, UPDATE_POLL_MS));
  }
}

//@ts-ignore
export default definePlugin((serverApi: ServerAPI) => {

  reportFailedUpdate(serverApi);

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
      serverApi.routerHook.removeRoute("/skullkey-content/:initActionSet/:initAction/:category?");
      serverApi.routerHook.removeRoute("/about-skullkey");
      unregister.unregister();
    },
  };
});
