import { t } from "../i18n";

/** A verified installation may still have an EA installer error to disclose. */
export function installerWarning(content?: { InstallerExitCode?: unknown }): string {
    const code = content?.InstallerExitCode;
    return typeof code === "number" && Number.isSafeInteger(code) && code !== 0
        ? t("ea_installer_warning", { code }) : "";
}
