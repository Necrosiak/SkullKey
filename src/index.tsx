import {
  definePlugin,
  Navigation,
  ServerAPI,
  showModal,
  staticClasses,
  useParams
} from "decky-frontend-lib";
import { FaKey } from "react-icons/fa";

import { Content } from "./ContentTabs";
import { About } from "./About";
import { MainMenuModal } from "./MainMenuModal";


//@ts-ignore
export default definePlugin((serverApi: ServerAPI) => {

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
    "/skeletonkey-content/:initActionSet/:initAction/:category?",
    () => {
      const { initActionSet, initAction, category } = useParams<{ initActionSet: string; initAction: string; category?: string }>();
      return <Content key={initActionSet + "_" + initAction + "_" + (category ?? "")} serverAPI={serverApi} initActionSet={initActionSet} initAction={initAction} category={category} />;
    },
    {
      exact: true,
    }
  );
  serverApi.routerHook.addRoute(
    "/about-skeletonkey",
    () => {
      return <About serverAPI={serverApi} />
    },
    {
      exact: true,
    }
  );

  return {
    title: <div className={staticClasses.Title}>SkeletonKey</div>,
    content: <Content serverAPI={serverApi} initActionSet="init" initAction="InitActions" />,
    icon: <FaKey />,
    onDismount() {
      serverApi.routerHook.removeRoute("/skeletonkey-content/:initActionSet/:initAction/:category?");
      serverApi.routerHook.removeRoute("/about-skeletonkey");
      unregister.unregister();
    },
  };
});
