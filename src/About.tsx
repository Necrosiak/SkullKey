// Settings & About page — fully rewritten for this fork (no upstream content).
// One sidebar: Settings / Dependencies / Logs / About (+ Developer). All
// user-facing text goes through i18n (t()).
import { ConfirmModal, DialogBody, DialogControlsSection, Focusable, Navigation, ServerAPI, SidebarNavigation, ToggleField, showModal } from "decky-frontend-lib";
import { VFC, useEffect, useRef, useState } from "react";
import { HiOutlineQrCode } from "react-icons/hi2";
import { SiEpicgames, SiGithub, SiGogdotcom } from "react-icons/si";
import { FaAmazon, FaDownload, FaFlask, FaShieldAlt, FaSyncAlt, FaTrashAlt } from "react-icons/fa";
import { showQrModal } from "./MainMenu";
import Logger from "./Utils/logger";
import { LogViewer } from "./LogViewer";
import { ScrollableWindowRelative } from './ScrollableWindow';
import { Developer } from "./Developer";
import { ActionCard, ACCENT } from "./Components/Styled";
import { t } from "./i18n";

const GITHUB_URL = "https://github.com/Necrosiak/SkullKey";

// Titled box with a colored left border — same language as the login cards.
const Section: VFC<{ title: string; color?: string; children?: any }> = ({ title, color, children }) => (
    <div style={{
        margin: "8px 0", padding: "10px 12px", borderRadius: 6,
        background: "rgba(255,255,255,0.04)",
        borderLeft: `3px solid ${color || ACCENT}`,
    }}>
        <div style={{
            fontSize: 13, fontWeight: 700, textTransform: "uppercase",
            letterSpacing: ".5px", color: color || ACCENT, marginBottom: 6,
        }}>{title}</div>
        {children}
    </div>
);

const StoreLine: VFC<{ icon: any; color: string; name: string; engine: string }> = ({ icon: Icon, color, name, engine }) => (
    <div style={{ display: "flex", alignItems: "center", gap: 8, padding: "3px 0", fontSize: 13 }}>
        <Icon size={14} style={{ color, flexShrink: 0 }} />
        <span style={{ fontWeight: 600, width: 110 }}>{name}</span>
        <span style={{ opacity: 0.6 }}>{t("powered_by", { engine })}</span>
    </div>
);

const UpdateSection: VFC<{ serverAPI: ServerAPI }> = ({ serverAPI }) => {
    const [version, setVersion] = useState("…");
    const [autoUpd, setAutoUpd] = useState(true);
    const [checking, setChecking] = useState(false);
    const [updating, setUpdating] = useState(false);
    const [updUrl, setUpdUrl] = useState("");
    const [updLabel, setUpdLabel] = useState("");

    useEffect(() => {
        serverAPI.callPluginMethod<{}, string>("get_version", {}).then((r) => r.success && setVersion(String(r.result)));
        serverAPI.callPluginMethod<{}, boolean>("get_autoupdate", {}).then((r) => r.success && setAutoUpd(!!r.result));
    }, []);

    const check = async () => {
        setChecking(true);
        setUpdLabel("");
        setUpdUrl("");
        try {
            const r = await serverAPI.callPluginMethod<{}, any>("check_update", {});
            if (r.success && r.result) {
                const info: any = r.result;
                if (info.update_available) {
                    setUpdUrl(info.url);
                    setUpdLabel(t("btn_install_update", { version: info.latest }));
                } else if (info.error) {
                    setUpdLabel(t("update_error"));
                } else {
                    setUpdLabel(t("up_to_date"));
                }
            } else {
                setUpdLabel(t("update_error"));
            }
        } catch (e) {
            setUpdLabel(t("update_error"));
        }
        setChecking(false);
    };

    const install = async () => {
        setUpdating(true);
        try { await serverAPI.callPluginMethod<{ url: string }, boolean>("apply_update", { url: updUrl }); } catch (e) { }
        // plugin_loader restarts right after — the QAM reloads by itself
    };

    return (
        <Section title={t("sec_updates")} color="#4caf50">
            <div style={{ fontSize: 12, opacity: 0.7, marginBottom: 8 }}>
                {t("current_version")} : <b>v{version}</b>
            </div>
            <ActionCard
                color="#4caf50"
                active={!!updUrl}
                disabled={checking || updating}
                onClick={updUrl ? install : check}
            >
                <FaDownload size={12} />
                <span>
                    {updating ? t("btn_updating")
                        : checking ? t("btn_checking")
                            : updUrl ? updLabel
                                : updLabel || t("btn_check_updates")}
                </span>
            </ActionCard>
            <ToggleField
                label={t("autoupdate")}
                description={t("autoupdate_desc")}
                checked={autoUpd}
                onChange={(v) => {
                    setAutoUpd(v);
                    serverAPI.callPluginMethod<{ enabled: boolean }, boolean>("set_autoupdate", { enabled: v }).catch(() => { });
                }}
            />
        </Section>
    );
};

const SettingsTab: VFC<{ serverAPI: ServerAPI }> = ({ serverAPI }) => {
    const [doubleStick, setDoubleStick] = useState(localStorage.getItem('sk_doubleStick') === 'true');
    const [logging, setLogging] = useState(localStorage.getItem('enableLogger') === 'true');
    const [devMode, setDevMode] = useState(localStorage.getItem('sk_developermode') === 'true');

    return (
        <div style={{ padding: "0 8px" }}>
            <Section title={t("sec_general")}>
                <ToggleField
                    label={t("quick_menu")}
                    description={t("quick_menu_desc")}
                    checked={doubleStick}
                    onChange={(v) => { setDoubleStick(v); localStorage.setItem('sk_doubleStick', String(v)); }}
                />
            </Section>
            <UpdateSection serverAPI={serverAPI} />
            <Section title={t("sec_advanced")} color="#ff9800">
                <ToggleField
                    label={t("ui_logging")}
                    description={t("ui_logging_desc")}
                    checked={logging}
                    onChange={(v) => { setLogging(v); localStorage.setItem('enableLogger', String(v)); }}
                />
                <ToggleField
                    label={t("dev_mode")}
                    description={t("dev_mode_desc")}
                    checked={devMode}
                    onChange={(v) => { setDevMode(v); localStorage.setItem('sk_developermode', String(v)); }}
                />
            </Section>
        </div>
    );
};

const DependenciesTab: VFC<{ serverAPI: ServerAPI }> = ({ serverAPI }) => {
    const logger = new Logger("Dependencies");
    const [output, setOutput] = useState("");
    const [isInstalling, setIsInstalling] = useState(false);
    const [reloading, setReloading] = useState(false);
    const textareaRef = useRef<HTMLTextAreaElement>(null);
    const socket = useRef<WebSocket | null>(null);

    useEffect(() => {
        serverAPI.callPluginMethod<{}, Number>("get_websocket_port", {}).then((port) => {
            const address = "ws://localhost:" + port.result + "/ws";
            socket.current = new WebSocket(address);
            socket.current.onmessage = (event) => {
                const message = JSON.parse(event.data);
                setOutput((prev) => prev + message.data + "\n");
                if (textareaRef.current !== null) {
                    textareaRef.current.scrollTop = textareaRef.current.scrollHeight;
                }
                if (message.status === "closed") {
                    setIsInstalling(false);
                }
            };
        });
        return () => { socket.current?.close(); };
    }, []);

    const sendAction = (action: string) => {
        try {
            if (socket.current) {
                setOutput("");
                setIsInstalling(true);
                socket.current.send(JSON.stringify({ action }));
            }
        } catch (e) {
            logger.error(e);
        }
    };

    const getRuntimeId = (name: string) => {
        // @ts-ignore
        const app = appStore.allApps.filter(a => a.display_name.startsWith(name));
        return app.length === 0 ? -1 : app[0].appid;
    };
    const isRuntimeInstalled = (name: string) => {
        try {
            // @ts-ignore
            return appStore.GetAppOverviewByAppID(getRuntimeId(name))?.local_per_client_data?.installed ?? false;
        } catch (e) { return false; }
    };

    return (
        <div style={{ padding: "0 8px" }}>
            <Section title={t("sec_deps")} color="#4caf50">
                <div style={{ fontSize: 12, opacity: 0.7, marginBottom: 8 }}>
                    {t("deps_desc")}
                </div>
                <Focusable style={{ display: "flex", gap: 6 }} flow-children="horizontal">
                    <div style={{ flex: 1 }}>
                        <ActionCard color="#4caf50" disabled={isInstalling} onClick={() => sendAction("install_dependencies")}>
                            <FaDownload size={12} />
                            <span>{isInstalling ? t("btn_working") : t("btn_install")}</span>
                        </ActionCard>
                    </div>
                    <div style={{ flex: 1 }}>
                        <ActionCard color="#67a3ff" disabled={reloading} onClick={async () => {
                            setReloading(true);
                            await serverAPI.callPluginMethod("reload", {});
                            setReloading(false);
                        }}>
                            <FaSyncAlt size={12} />
                            <span>{reloading ? t("btn_reloading") : t("btn_reload")}</span>
                        </ActionCard>
                    </div>
                    <div style={{ flex: 1 }}>
                        <ActionCard color="#f44336" disabled={isInstalling} onClick={() =>
                            showModal(<ConfirmModal strTitle={t("confirm")} strDescription={t("uninstall_deps_q")}
                                onOK={() => sendAction("uninstall_dependencies")} />)
                        }>
                            <FaTrashAlt size={12} />
                            <span>{t("btn_uninstall")}</span>
                        </ActionCard>
                    </div>
                </Focusable>
                {output !== "" && (
                    <textarea
                        ref={textareaRef}
                        readOnly
                        style={{
                            width: "100%", height: 180, marginTop: 10, boxSizing: "border-box",
                            background: "#0d0d0d", color: "#9ccc65", border: "1px solid rgba(255,255,255,0.1)",
                            borderRadius: 6, fontFamily: "monospace", fontSize: 11, padding: 8,
                        }}
                        value={output}
                    />
                )}
            </Section>
            <Section title={t("sec_anticheat")} color="#ff9800">
                <div style={{ fontSize: 12, opacity: 0.7, marginBottom: 8 }}>
                    {t("anticheat_desc")}
                </div>
                <Focusable style={{ display: "flex", gap: 6 }} flow-children="horizontal">
                    <div style={{ flex: 1 }}>
                        <ActionCard color="#ff9800" disabled={isRuntimeInstalled("Proton EasyAntiCheat Runtime")} onClick={() => {
                            SteamClient.Installs.OpenInstallWizard([getRuntimeId("Proton EasyAntiCheat Runtime")]);
                        }}>
                            <FaShieldAlt size={12} />
                            <span>{isRuntimeInstalled("Proton EasyAntiCheat Runtime") ? "EasyAntiCheat ✓" : "EasyAntiCheat"}</span>
                        </ActionCard>
                    </div>
                    <div style={{ flex: 1 }}>
                        <ActionCard color="#ff9800" disabled={isRuntimeInstalled("Proton BattlEye Runtime")} onClick={() => {
                            SteamClient.Installs.OpenInstallWizard([getRuntimeId("Proton BattlEye Runtime")]);
                        }}>
                            <FaShieldAlt size={12} />
                            <span>{isRuntimeInstalled("Proton BattlEye Runtime") ? "BattlEye ✓" : "BattlEye"}</span>
                        </ActionCard>
                    </div>
                </Focusable>
            </Section>
        </div>
    );
};

const AboutTab: VFC = () => (
    <div style={{ padding: "0 8px", height: "100%", display: "flex" }}>
        <ScrollableWindowRelative>
            <Section title={t("sec_plugin")}>
                <div style={{ fontSize: 13, lineHeight: 1.5 }} dangerouslySetInnerHTML={{ __html: t("about_desc") }} />
                <div style={{ marginTop: 10 }}>
                    <StoreLine icon={SiEpicgames} color="#26bbff" name="Epic Games" engine="Legendary" />
                    <StoreLine icon={SiGogdotcom} color="#a24bfa" name="GOG" engine="gogdl" />
                    <StoreLine icon={FaAmazon} color="#ff9900" name="Amazon Games" engine="nile" />
                </div>
            </Section>
            <Section title={t("sec_project")} color="#67a3ff">
                <Focusable style={{ display: "flex", gap: 6, alignItems: "center" }} flow-children="horizontal">
                    <div style={{ flex: 1 }}>
                        <ActionCard color="#67a3ff" center={false} onClick={() => Navigation.NavigateToExternalWeb(GITHUB_URL)}>
                            <SiGithub size={13} />
                            <span style={{ flex: 1, textAlign: "left" }}>{t("github_line", { repo: "Necrosiak/SkullKey" })}</span>
                        </ActionCard>
                    </div>
                    <div style={{ width: 52 }}>
                        <ActionCard color="#67a3ff" onClick={() => showQrModal(GITHUB_URL)}>
                            <HiOutlineQrCode size={14} />
                        </ActionCard>
                    </div>
                </Focusable>
            </Section>
            <Section title={t("sec_credits")} color="#a24bfa">
                <div style={{ fontSize: 12, lineHeight: 1.6, opacity: 0.85 }}>
                    <span dangerouslySetInnerHTML={{ __html: t("credits_base") }} />
                    <br />
                    <span dangerouslySetInnerHTML={{ __html: t("credits_engines") }} />
                    <br />
                    {t("credits_independent")}
                </div>
            </Section>
        </ScrollableWindowRelative>
    </div>
);

export const About: VFC<{ serverAPI: ServerAPI; }> = ({ serverAPI }) => {
    const [isDeveloperMode] = useState(localStorage.getItem('sk_developermode') === "true");

    return (
        <DialogBody>
            <DialogControlsSection style={{ height: "calc(100%)" }}>
                <SidebarNavigation key="1" pages={[
                    {
                        title: t("tab_settings"),
                        content: <SettingsTab serverAPI={serverAPI} />
                    },
                    {
                        title: t("tab_deps"),
                        content: <DependenciesTab serverAPI={serverAPI} />
                    },
                    {
                        title: t("tab_logs"),
                        content: <LogViewer serverAPI={serverAPI}></LogViewer>
                    },
                    {
                        title: t("tab_about"),
                        content: <AboutTab />
                    },
                    {
                        title: t("tab_dev"),
                        visible: isDeveloperMode,
                        content: <div style={{ padding: "0 8px" }}>
                            <Section title={t("sec_devtools")} color="#f44336">
                                <div style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 12, opacity: 0.7, marginBottom: 6 }}>
                                    <FaFlask size={12} />
                                    <span>{t("devtools_desc")}</span>
                                </div>
                                <Developer serverAPI={serverAPI} />
                            </Section>
                        </div>
                    }
                ]}
                    showTitle
                />
            </DialogControlsSection >
        </DialogBody >
    );
};
