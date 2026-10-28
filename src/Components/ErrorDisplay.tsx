import { ContentError } from "../Types/Types";
import { t } from "../i18n";

const bytes = (n?: number) => {
    const gb = (n || 0) / 2 ** 30;
    return gb >= 1 ? `${gb.toFixed(1)} GB` : `${Math.max(1, Math.round((n || 0) / 2 ** 20))} MB`;
};

/** The sentence a player can act on for a cause found by the backend, or "". */
export function errorText(code?: string, vars?: { Need?: number; Free?: number; Drive?: string }): string {
    if (!code || code === "unknown") return "";
    const key = `err_${code}`;
    const text = t(key, { need: bytes(vars?.Need), free: bytes(vars?.Free), drive: vars?.Drive || "" });
    return text === key ? "" : text;
}

export const ErrorDisplay = ({ error }: { error: ContentError; }) => {
    const clear = errorText(error.Code, error);
    // With a known cause the tool's own words become details; otherwise they
    // are the message.
    const details = clear ? [error.Message, error.Data].filter(Boolean).join("<br />") : error.Data;
    return (
        <div>
            <div style={{ fontSize: "1.1em", lineHeight: 1.4, whiteSpace: "pre-line" }}>
                {clear || error.Message || t("err_unknown")}
            </div>
            {details && (
                <div style={{ marginTop: "10px", fontSize: "0.85em", opacity: 0.7 }}>
                    <div>{t("err_details")}</div>
                    <div dangerouslySetInnerHTML={{ __html: details }}></div>
                </div>
            )}
            {error.LogPath && (
                <div style={{ marginTop: "10px", fontSize: "0.85em", opacity: 0.7, wordBreak: "break-all" }}>
                    {t("err_log_saved", { path: error.LogPath })}
                </div>
            )}
            {(error.ActionSet || error.ActionName) && (
                <div style={{ marginTop: "6px", fontSize: "0.75em", opacity: 0.45 }}>
                    {[error.ActionSet, error.ActionName].filter(Boolean).join(" · ")}
                </div>
            )}
        </div>
    );
};
