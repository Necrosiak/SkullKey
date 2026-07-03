import { DialogBody, DialogControlsSection, ServerAPI, SidebarNavigation, SidebarNavigationPage, Tab, Tabs } from "decky-frontend-lib";
import { VFC, useEffect, useState } from "react";
import { ActionSet, ContentType, ContentError, ContentResult, ExecuteArgs, ExecuteGetContentArgs, StoreContent, StoreTabsContent, GameDataList } from "./Types/Types";
import Logger from "./Utils/logger";
import { executeAction } from "./Utils/executeAction";
import { Loading } from "./Components/Loading";
import { ErrorDisplay } from "./Components/ErrorDisplay";
import { GridContent, contentTabsContainerClass } from "./Components/GridContent";
import { HtmlContent } from "./HtmlContent";
import { TextContent } from "./TextContent";
import { MainMenu } from "./MainMenu";
import { useCachedState } from './hooks/useCachedState';
import { gamepadLibraryClasses } from './staticClasses';
import { storeTheme } from './Components/Styled';
import { tabLabel } from './i18n';
interface ContentTabsProperties {
    serverAPI: ServerAPI;
    content: StoreTabsContent;
    initActionSet: string;
    initAction: string;
    layout: 'horizontal' | 'vertical';
    subActionSet: string;
    category?: string;
}
export interface StoreTabsState {
    currentTab: string;
}

export const ContentTabs: VFC<ContentTabsProperties> = ({ serverAPI, content, initAction, initActionSet, layout, subActionSet, category }) => {
    const logger = new Logger("StoreTabs");
    const { cacheState: cacheData, setCacheState: setCacheData } = useCachedState(initActionSet, initAction, 'tabcontent', { currentTab: "-1" });

    // Game stores (Epic/GOG/Amazon) and media/apps live in separate menus: when
    // a category is supplied only its tabs show in this top bar.
    const tabs = category
        ? content.Tabs.filter((t) => (t.Category ?? "games") === category)
        : content.Tabs;

    // The QAM store cards can force which tab opens (one-shot key).
    useEffect(() => {
        try {
            const forced = localStorage.getItem("sk_forced_tab");
            if (forced !== null) {
                localStorage.removeItem("sk_forced_tab");
                setCacheData({ currentTab: forced });
            }
        } catch (e) { }
    }, []);

    const getTabs: () => Tab[] = () => {
        return tabs.map((tab, index) => {
            const theme = storeTheme(tab.Title);
            return {
                title: (
                    <span style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
                        <span style={{ width: 8, height: 8, borderRadius: 4, background: theme.color, display: "inline-block" }} />
                        {tabLabel(tab.Title)}
                    </span>
                ) as any,
                content: <Content key={tab.ActionId} serverAPI={serverAPI} initActionSet={subActionSet} initAction={tab.ActionId} />,
                id: index.toString()
            };
        });
    };

    const getPages: () => SidebarNavigationPage[] = () => {
        return tabs.map((tab) => ({
            title: tabLabel(tab.Title),
            content: <Content key={tab.ActionId} serverAPI={serverAPI} initActionSet={subActionSet} initAction={tab.ActionId} />,
            identifier: tab.Title,
            hideTitle: true
        }));
    };

    return (
        <DialogBody key={initActionSet + "_" + initAction} className={contentTabsContainerClass}>
            {tabs.length === 0 ? <Loading /> : (layout === "horizontal" ? (
                <DialogControlsSection key={initActionSet + "_" + initAction + "horizontal"} className={gamepadLibraryClasses.GamepadLibrary}>
                    <Tabs
                        key="0"
                        activeTab={cacheData.currentTab}
                        onShowTab={(tabID: string) => setCacheData({ currentTab: tabID })}
                        tabs={getTabs()}
                        autoFocusContents={true}
                        //@ts-ignore
                        canBeHeaderBackground={'always'}
                    />
                </DialogControlsSection>
            ) : (
                <DialogControlsSection key={initActionSet + "_" + initAction + "vertical"} style={{ height: "100%" }}>
                    <SidebarNavigation key="1" pages={getPages()} />
                </DialogControlsSection>
            ))}
        </DialogBody>
    );
};

export const Content: VFC<{ serverAPI: ServerAPI; initActionSet: string; initAction: string; closeModal?: ()=>void; category?: string}> = ({ serverAPI, initActionSet, initAction, closeModal, category }) => {
    const logger = new Logger("Content");
    const [content, setContent] = useState<ContentResult<ContentType>>({ Type: "Empty", Content: {} });
    const [actionSetName, setActionSetName] = useState("");

    const { cacheState: gridContentCache, setCacheState: setGridContentCache, hadCache: hadGridCache } = useCachedState(
        initActionSet,
        initAction,
        'gridcontentparams',
        {
            filter: "",
            installed: false,
        }
    );

    useEffect(() => {
        (async () => {
            try {
                logger.debug(`Initializing Content with initActionSet: ${initActionSet} and initAction: ${initAction}`);
                const actionSetRes = await executeAction<ExecuteArgs,ActionSet>(serverAPI, initActionSet, initAction, {});
                logger.debug("init result: ", actionSetRes);
                if (actionSetRes === null) return;

                const actionSet = actionSetRes.Content;
                logger.debug(`Getting Content ${hadGridCache ? 'with args cache' : ''}`, hadGridCache ? gridContentCache : '');
                const contentRes = await getContent(actionSet.SetName, hadGridCache ? stringifyArgs(gridContentCache) : {});
                logger.debug("GetContent result: ", contentRes);
                if (contentRes === null) return;

                setActionSetName(actionSet.SetName);
                setContent(contentRes);
            } catch (error) {
                logger.error("OnInit: ", error);
            }
        })();
    }, []);

    const getContent = async (actionSet: string, actionArgs: { [param: string]: string; }) => executeAction<ExecuteGetContentArgs, ContentResult<ContentType>>(serverAPI, actionSet, "GetContent", actionArgs);

    const refreshContent = (args: { [param: string]: any; }, onFinish?: () => void) => {
        (async () => {
            logger.debug("Refreshing Content with args: ", args);
            const contentRes = await getContent(actionSetName, stringifyArgs(args));
            if (contentRes === null) {
                return;
            }
            setContent(contentRes);
            onFinish?.();
        })();
    };

    switch (content.Type) {
        case "GameGrid":
            return <GridContent
                serverAPI={serverAPI}
                content={content.Content as GameDataList}
                initActionSet={actionSetName}
                refreshContent={refreshContent}
                argsCache={gridContentCache}
                setArgsCache={setGridContentCache}
            />;

        case "StoreTabs":
            return <ContentTabs
                serverAPI={serverAPI}
                content={content.Content as StoreTabsContent}
                layout="horizontal"
                initAction={initAction}
                initActionSet={initActionSet}
                subActionSet={actionSetName}
                category={category}
            />;

        case "SideBarPage":
            return <ContentTabs
                serverAPI={serverAPI}
                content={content.Content as StoreTabsContent}
                layout="vertical"
                initAction={initAction}
                initActionSet={initActionSet}
                subActionSet={actionSetName}
                category={category}
            />;

        case "MainMenu":
            return <MainMenu //key={initActionSet + "_" + initAction} 
                serverApi={serverAPI}
                content={content.Content as StoreContent}
                initActionSet={actionSetName}
                initAction=""
                closeModal={closeModal}
            />;

        case "Text":
            return <TextContent //key={initActionSet + "_" + initAction} 
                content={content.Content as string}
            />;

        case "Html":
            return <HtmlContent //key={initActionSet + "_" + initAction}
                content={content.Content as string}
            />;

        case "Error":
            return <ErrorDisplay //key={initActionSet + "_" + initAction}
                error={content.Content as ContentError}
            />;

        case "Empty":
            return <Loading />;

        default:
            return null;
    }
};

function stringifyArgs(args: { [param: string]: any; }) {
    let out: { [param: string]: string; } = {};
    for (let key in args) {
        out[key] = String(args[key]);
    }
    return out;
}