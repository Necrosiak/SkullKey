import { DialogButton, Focusable, ModalRoot, ProgressBar, ServerAPI, TextField, showModal } from "decky-frontend-lib";
import { useEffect, useRef, useState, VFC } from "react";
import { t } from "../i18n";
import { executeAction } from "../Utils/executeAction";
import { configureShortcut, runApp } from "../Utils/utils";
import { pickInstallDrive } from "./DrivePicker";
import { Candidate, defaultCandidate, FlowEvent, FlowState, initialState, nextStep, SourceKind } from "../disksFlow";

const SET = "DisksActions";
const IMAGE_RE = /\.(iso|cue|bin|mdf|mds|img|nrg)$/i;
const EXE_RE = /\.exe$/i;
const FILE = 0 as any, FOLDER = 1 as any;          // decky FileSelectionType (const enum)

interface Entry { kind: string; path: string; parts: string[]; label: string; }
interface Optical { device: string; mountpoint: string; label: string; }

async function call<T = any>(serverAPI: ServerAPI, action: string, args: Record<string, string>): Promise<any> {
    const res = await executeAction<any, any>(serverAPI, SET, action, args);
    return res as T;
}

async function pick(serverAPI: ServerAPI, folder: boolean, start: string, re?: RegExp) {
    try {
        const res = folder
            ? await serverAPI.openFilePickerV2(FOLDER, start, false, true)
            : await serverAPI.openFilePickerV2(FILE, start, true, true, re);
        return res?.path || "";
    } catch {
        return "";
    }
}

async function guessTitle(serverAPI: ServerAPI, path: string) {
    const r = await call(serverAPI, "GetTitle", { path });
    return r?.Content?.Message || path.split("/").pop() || "";
}

async function applyLaunch(serverAPI: ServerAPI, slug: string, id: number) {
    const res = await call(serverAPI, "Install", { shortname: slug, steamClientID: String(id) });
    if (res?.Type !== "LaunchOptions") throw new Error(res?.Content?.Message || "install");
    const lo = res.Content;
    const proton = (window as any).settingsStore?.settings?.strCompatTool;
    configureShortcut(id, { ...lo, CompatToolName: proton || "proton_experimental" });
    return lo;
}

async function applyArtwork(serverAPI: ServerAPI, slug: string, id: number) {
    const res = await call(serverAPI, "GetJsonImages", { shortname: slug });
    const img = res?.Content || {};
    const slots: [string, number][] = [["Grid", 0], ["Hero", 1], ["Logo", 2], ["GridH", 3]];
    for (const [key, asset] of slots) {
        if (img[key]) await SteamClient.Apps.SetCustomArtworkForApp(id, img[key], img[key + "Type"] || "png", asset);
    }
}

export const DiskAddModal: VFC<{ serverAPI: ServerAPI; closeModal?: () => void; onDone: () => void;
                                 changeExe?: { slug: string; steamClientID: string } }> =
    ({ serverAPI, closeModal, onDone, changeExe }) => {
    const [state, setState] = useState<FlowState>(changeExe ? { step: "exe-loading" } : initialState());
    const [entries, setEntries] = useState<Entry[] | null>(null);
    const [optical, setOptical] = useState<Optical[] | null>(null);
    const [progress, setProgress] = useState(0);
    const [title, setTitle] = useState("");
    const [selected, setSelected] = useState<string>("");
    const slug = useRef(changeExe?.slug || "");
    const appId = useRef(changeExe ? parseInt(changeExe.steamClientID) : 0);
    const lastScan = useRef("");
    const alive = useRef(true);
    useEffect(() => () => { alive.current = false; }, []);

    const send = (e: FlowEvent) => setState(s => nextStep(s, e));
    const fail = (message: string) => send({ type: "error", message });

    useEffect(() => {
        call(serverAPI, "GetSources", {}).then(r => { lastScan.current = r?.Content?.last_scan_dir || ""; });
    }, []);
    useEffect(() => { if (state.step === "title") setTitle(state.title || ""); }, [state.step]);

    // drive → add → wait for the worker
    useEffect(() => {
        if (state.step !== "drive") return;
        (async () => {
            const drive = await pickInstallDrive(serverAPI);
            if (drive === null) return send({ type: "cancel" });
            await serverAPI.callPluginMethod("set_install_root", { path: drive });
            send({ type: "drive", root: drive });
        })();
    }, [state.step]);

    useEffect(() => {
        if (state.step !== "preparing") return;
        let stop = false;
        (async () => {
            const payload = JSON.stringify({ kind: state.kind, path: state.path, parts: state.parts, title: state.title });
            const res = await call(serverAPI, "Download", { payload });
            if (res?.Type !== "Progress") return fail(res?.Content?.Message || t("disks_err_prepare"));
            slug.current = res.Content.ShortName;
            while (!stop) {
                const p = await call(serverAPI, "GetProgress", { shortname: slug.current });
                const c = p?.Content || {};
                if (c.Error) return fail(c.Error);
                setProgress(c.Percentage || 0);
                if (c.Percentage >= 100) break;
                await new Promise(r => setTimeout(r, 1000));
            }
            const details = await call(serverAPI, "GetStage", { shortname: slug.current });
            const id = await SteamClient.Apps.AddShortcut(state.title || "Game", "/bin/bash", "", "");
            appId.current = id;
            SteamClient.Apps.SetShortcutName(id, state.title || "Game");
            send({ type: "prepared", stage: details?.Content?.Message || "ready" });
        })().catch(e => fail(String(e?.message || e)));
        return () => { stop = true; };
    }, [state.step]);

    // installer runs as the game's own shortcut (visible in gamescope)
    useEffect(() => {
        if (state.step !== "installer-ready") return;
        (async () => {
            await applyLaunch(serverAPI, slug.current, appId.current);
            for (let i = 0; i < 20 && !appStore.GetAppOverviewByAppID(appId.current); i++) {
                await new Promise(r => setTimeout(r, 250));
            }
            const resume = { slug: slug.current, steamClientID: String(appId.current) };
            runApp(appId.current, () => {
                if (alive.current) send({ type: "installerClosed" });
                else openDiskAdd(serverAPI, onDone, resume);
            });
            send({ type: "installerStarted" });
        })().catch(e => fail(String(e?.message || e)));
    }, [state.step]);

    useEffect(() => {
        if (state.step !== "exe-loading") return;
        call(serverAPI, "Finalize", { shortname: slug.current }).then(r => {
            const list: Candidate[] = r?.Content?.candidates || [];
            setSelected(defaultCandidate(list)?.path || list[0]?.path || "");
            send({ type: "candidates", list });
        });
    }, [state.step]);

    useEffect(() => {
        if (state.step !== "done") return;
        (async () => {
            const r = await call(serverAPI, "SetExe", { shortname: slug.current, exe: state.exe || "" });
            if (r?.Type !== "Success") return fail(r?.Content?.Message || "exe");
            await applyLaunch(serverAPI, slug.current, appId.current);
            await applyArtwork(serverAPI, slug.current, appId.current);
            onDone();
            closeModal?.();
        })().catch(e => fail(String(e?.message || e)));
    }, [state.step]);

    const cancel = async () => {
        if (!changeExe && slug.current) {
            await call(serverAPI, "CancelInstall", { shortname: slug.current });
            if (appId.current) SteamClient.Apps.RemoveShortcut(appId.current);
        }
        send({ type: "cancel" });
        closeModal?.();
    };

    const chooseSource = async (kind: SourceKind | "scan" | "disc") => {
        const start = lastScan.current || "/home";
        if (kind === "image" || kind === "installer") {
            const path = await pick(serverAPI, false, start, kind === "image" ? IMAGE_RE : EXE_RE);
            if (path) send({ type: "source", kind, path, label: await guessTitle(serverAPI, path) });
        } else if (kind === "ready") {
            const path = await pick(serverAPI, true, start);
            if (path) send({ type: "source", kind, path, label: await guessTitle(serverAPI, path) });
        } else if (kind === "scan") {
            const dir = await pick(serverAPI, true, start);
            if (!dir) return;
            const r = await call(serverAPI, "Scan", { folder: dir });
            setEntries(r?.Content?.entries || []);
        } else if (kind === "disc") {
            const r = await call(serverAPI, "GetSources", {});
            for (const dev of r?.Content?.unmounted || []) await call(serverAPI, "Mount", { device: dev });
            const again = await call(serverAPI, "GetSources", {});
            setOptical(again?.Content?.optical || []);
        }
    };

    const box = { display: "flex", flexDirection: "column" as const, gap: "8px" };
    const head = (text: string) => <div style={{ fontWeight: "bold", fontSize: "1.2em", marginBottom: "12px" }}>{text}</div>;

    let body: JSX.Element;
    switch (state.step) {
        case "source":
            body = entries ? (
                <Focusable style={box}>
                    {head(t("disks_scan_results"))}
                    {entries.length === 0 && <div>{t("disks_scan_empty")}</div>}
                    {entries.map((e, i) => (
                        <DialogButton key={e.path} autoFocus={i === 0} onClick={() =>
                            send({ type: "source", kind: e.kind === "folder" ? "folder" : e.kind as SourceKind,
                                   path: e.path, parts: e.parts, label: e.label })}>
                            {e.label} · {t("disks_kind_" + e.kind)}
                        </DialogButton>
                    ))}
                    <DialogButton onClick={() => setEntries(null)}>{t("disks_back")}</DialogButton>
                </Focusable>
            ) : optical ? (
                <Focusable style={box}>
                    {head(t("disks_src_disc"))}
                    {optical.length === 0 && <div>{t("disks_no_disc")}</div>}
                    {optical.map((o, i) => (
                        <DialogButton key={o.device} autoFocus={i === 0} onClick={() =>
                            send({ type: "source", kind: "optical", path: o.mountpoint, label: o.label })}>
                            {o.label}
                        </DialogButton>
                    ))}
                    <DialogButton onClick={() => chooseSource("disc")}>{t("disks_refresh")}</DialogButton>
                    <DialogButton onClick={() => setOptical(null)}>{t("disks_back")}</DialogButton>
                </Focusable>
            ) : (
                <Focusable style={box}>
                    {head(t("disks_add_title"))}
                    <DialogButton autoFocus onClick={() => chooseSource("image")}>{t("disks_src_image")}</DialogButton>
                    <DialogButton onClick={() => chooseSource("disc")}>{t("disks_src_disc")}</DialogButton>
                    <DialogButton onClick={() => chooseSource("installer")}>{t("disks_src_installer")}</DialogButton>
                    <DialogButton onClick={() => chooseSource("ready")}>{t("disks_src_ready")}</DialogButton>
                    <DialogButton onClick={() => chooseSource("scan")}>{t("disks_src_scan")}</DialogButton>
                </Focusable>
            );
            break;
        case "title":
            body = (
                <Focusable style={box}>
                    {head(t("disks_title_prompt"))}
                    <TextField value={title} onChange={e => setTitle(e.target.value)}
                        onKeyDown={(e: any) => { if (e.key === "Enter" && title.trim()) send({ type: "title", title }); }} />
                    <DialogButton disabled={!title.trim()} onClick={() => send({ type: "title", title })}>{t("disks_next")}</DialogButton>
                </Focusable>
            );
            break;
        case "exe-choose":
        case "exe-manual":
            body = (
                <Focusable style={box}>
                    {head(t("disks_choose_exe"))}
                    {(state.candidates || []).map((c, i) => (
                        <DialogButton key={c.path} autoFocus={c.path === selected || (!selected && i === 0)}
                            onClick={() => send({ type: "exe", path: c.path })}>
                            {c.path.split("/").slice(-2).join("/")}
                        </DialogButton>
                    ))}
                    <DialogButton onClick={async () => {
                        const path = await pick(serverAPI, false, "/home", EXE_RE);
                        if (path) send({ type: "exe", path });
                    }}>{t("disks_browse_exe")}</DialogButton>
                </Focusable>
            );
            break;
        case "error":
            body = <Focusable style={box}>{head(t("disks_error"))}<div>{state.message}</div>
                <DialogButton onClick={cancel}>{t("btn_cancel")}</DialogButton></Focusable>;
            break;
        default:
            body = (
                <Focusable style={box}>
                    {head(state.step === "installer-running" ? t("disks_installer_running") : t("disks_preparing"))}
                    {state.step === "preparing" && <ProgressBar nProgress={progress} />}
                    <DialogButton onClick={cancel}>{t("btn_cancel")}</DialogButton>
                </Focusable>
            );
    }
    const close = () => { if (["source", "title", "error"].includes(state.step)) closeModal?.(); };
    return <ModalRoot onCancel={close} closeModal={() => closeModal?.()}>{body}</ModalRoot>;
};

export function openDiskAdd(serverAPI: ServerAPI, onDone: () => void, changeExe?: { slug: string; steamClientID: string }) {
    const modal = showModal(<DiskAddModal serverAPI={serverAPI} onDone={onDone} changeExe={changeExe}
        closeModal={() => modal.Close()} />);
}
