import { DialogButton, Focusable, ModalRoot, ServerAPI, showModal } from "decky-frontend-lib";
import { t } from "../i18n";

export interface Drive {
    path: string;
    label: string;
    free: number;
    total: number;
    system: boolean;
    kind?: string;
}

const size = (bytes: number) => {
    const gb = bytes / 2 ** 30;
    return gb >= 1024 ? `${(gb / 1024).toFixed(1)} TB` : `${Math.floor(gb)} GB`;
};

// Asks where to install. Resolves with "" for the system drive (each store
// keeps its usual folder), a mount path for another drive, or null if the
// user backed out. With a single drive, nothing is shown.
export async function pickInstallDrive(serverAPI: ServerAPI): Promise<string | null> {
    const res = await serverAPI.callPluginMethod<{}, Drive[]>("list_drives", {});
    const drives = res.success && Array.isArray(res.result) ? res.result : [];
    if (drives.length < 2) return "";
    return new Promise((resolve) => {
        let done = false;
        let modal: { Close: () => void } | null = null;
        const finish = (value: string | null) => {
            if (done) return;
            done = true;
            resolve(value);
            modal?.Close();
        };
        modal = showModal(
            <ModalRoot onCancel={() => finish(null)} closeModal={() => finish(null)}>
                <div style={{ fontWeight: "bold", fontSize: "1.2em", marginBottom: "12px" }}>{t("install_on")}</div>
                <Focusable style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
                    {drives.map((d, i) => (
                        <DialogButton key={d.path} autoFocus={i === 0} onClick={() => finish(d.system ? "" : d.path)}>
                            {(d.system ? t("drive_system") : d.label) + (d.kind ? ` · ${d.kind === "sd" ? "SD" : d.kind.toUpperCase()}` : "") + " — " + t("drive_free", { free: size(d.free), total: size(d.total) })}
                        </DialogButton>
                    ))}
                </Focusable>
            </ModalRoot>
        );
    });
}
