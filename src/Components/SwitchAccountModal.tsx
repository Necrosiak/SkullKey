import { DialogButton, Focusable, ModalRoot, ServerAPI } from "decky-frontend-lib";
import { VFC, useState } from "react";
import { notify } from "./Styled";
import { t } from "../i18n";

// ── Changer de compte sans se déconnecter ───────────────────────────────────
// Chaque compte garde sa session sur l'appareil (scripts/accounts.py) : on
// bascule de l'un à l'autre, ou on en ajoute un, sans déconnexion du magasin.
export const accountName = (username: string) => (username || "").split(" · ")[0].trim();

export const callAccounts = async (serverAPI: ServerAPI, actionSet: string, args: Record<string, string>) => {
    const r = await serverAPI.callPluginMethod<{}, any>("execute_action", { actionSet, actionName: "Accounts", ...args });
    return r.success ? r.result : null;
};

export const SwitchAccountModal: VFC<{
    closeModal?: () => void; serverAPI: ServerAPI; actionSet: string; current: string;
    saved: string[]; onSwitched: (name: string) => void; onAdd: () => void;
}> = ({ closeModal, serverAPI, actionSet, current, saved, onSwitched, onAdd }) => {
    const [names, setNames] = useState<string[]>(saved.filter(n => n.toLowerCase() !== current.toLowerCase()));
    const [busy, setBusy] = useState(false);
    const fail = (r: any) => notify({ title: t("switch_account"),
        body: r?.Content?.Message === "busy" ? t("switch_busy") : t("switch_failed") });
    const pick = async (name: string) => {
        setBusy(true);
        const r = await callAccounts(serverAPI, actionSet, { action: "switch", current, target: name });
        setBusy(false);
        if (r?.Type !== "Accounts") return fail(r);
        closeModal?.();
        onSwitched(name);
    };
    const add = async () => {
        setBusy(true);
        const r = await callAccounts(serverAPI, actionSet, { action: "new", current });
        setBusy(false);
        if (r?.Type !== "Accounts") return fail(r);
        closeModal?.();
        onAdd();
    };
    const forget = async (name: string) => {
        const r = await callAccounts(serverAPI, actionSet, { action: "forget", current: name });
        if (r?.Type === "Accounts") setNames((r.Content?.Saved || []).filter((n: string) => n.toLowerCase() !== current.toLowerCase()));
    };
    return (
        <ModalRoot closeModal={closeModal}>
            <h2 style={{ margin: "0 0 6px" }}>{t("switch_account")}</h2>
            <div style={{ opacity: 0.75, marginBottom: 14 }}>{t("switch_desc")}</div>
            <Focusable style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                {names.map(name => (
                    <Focusable key={name} style={{ display: "flex", gap: 8 }} flow-children="horizontal">
                        <DialogButton style={{ flex: 1 }} disabled={busy} onClick={() => pick(name)}>{name}</DialogButton>
                        <DialogButton style={{ width: 120, minWidth: 0 }} disabled={busy} onClick={() => forget(name)}>{t("switch_forget")}</DialogButton>
                    </Focusable>
                ))}
                <DialogButton disabled={busy} onClick={add}>＋ {t("switch_add")}</DialogButton>
            </Focusable>
        </ModalRoot>
    );
};
