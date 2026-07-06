// Shared visual kit — same design language as the BC250-Toolkit / Steamcord
// plugins: focusable cards with a white halo + colored glow on gamepad focus,
// one accent color per store, native Steam notifications.
import { DialogButton } from "decky-frontend-lib";
import { useState } from "react";
import { SiEpicgames, SiGogdotcom, SiMihoyo } from "react-icons/si";
import { FaAmazon, FaBoxOpen, FaTv, FaMusic, FaCloud, FaThLarge, FaSkull } from "react-icons/fa";

const Btn = DialogButton as any;

export const ACCENT = "#5865f2";

export interface StoreTheme {
    color: string;
    icon: any;
}

// Accent color + icon per store / media section. Keyed on either the tab title
// ("TV & Video", "Music"…) or the ActionSet name ("MediaTvActions"…) so the
// theme stays consistent between the tab bar and the game page.
export function storeTheme(name?: string): StoreTheme {
    const n = (name || "").toLowerCase();
    if (n.includes("epic")) return { color: "#26bbff", icon: SiEpicgames };
    if (n.includes("gog")) return { color: "#a24bfa", icon: SiGogdotcom };
    if (n.includes("amazon")) return { color: "#ff9900", icon: FaAmazon };
    if (n.includes("mihoyo") || n.includes("hoyo")) return { color: "#4d8dff", icon: SiMihoyo };
    // "Classics Reborn" tab (title) / PortsActions (SetName): revived console
    // classics — skull icon to match the SkullKey theme.
    if (n.includes("ports") || n.includes("classic")) return { color: "#c8a24b", icon: FaSkull };
    // media sections — match SetName ("mediatvactions") and tab title
    if (n.includes("mediatv") || n.startsWith("tv")) return { color: "#e5484d", icon: FaTv };
    if (n.includes("mediamusic") || n.startsWith("music")) return { color: "#30a46c", icon: FaMusic };
    if (n.includes("mediacloud") || n.startsWith("cloud")) return { color: "#00bcd4", icon: FaCloud };
    if (n.includes("mediaapps") || n.startsWith("apps")) return { color: "#eab308", icon: FaThLarge };
    return { color: ACCENT, icon: FaBoxOpen };
}

// Native Steam notification (popup + sound). The Decky toaster creates
// malformed entries without notification_type on this Steam build, which can
// crash the notifications panel — DisplayClientNotification is a transparent
// replacement (title/body).
export function notify(data: { title?: string; body: string; duration?: number }) {
    try {
        const App = (window as any).App;
        const steamid = App?.GetCurrentUser?.()?.strSteamID || App?.m_CurrentUser?.strSteamID || "";
        // steamid is mandatory: without it the entry is malformed and crashes
        // the Steam notifications panel — better not to notify at all.
        if (!steamid) return;
        (window as any).SteamClient?.ClientNotifications?.DisplayClientNotification?.(
            1,
            JSON.stringify({ title: data.title || "SkullKey", body: data.body, state: "active", steamid }),
            () => { },
        );
    } catch (e) { console.error("[SkullKey] notify failed", e); }
}

// Clickable card: colored background when active, white halo + colored glow
// on gamepad focus.
export function CardBtn({ active, focused, color, disabled, center, big, onClick, onFocus, onBlur, children }: any) {
    const c = color || ACCENT;
    return (
        <Btn
            disabled={disabled}
            onClick={onClick}
            onFocus={onFocus}
            onBlur={onBlur}
            style={{
                display: "flex", alignItems: "center", justifyContent: center ? "center" : "flex-start",
                gap: 8, width: "100%", minWidth: 0,
                padding: big ? "12px 14px" : "7px 10px", margin: 0, minHeight: 0, boxSizing: "border-box",
                borderRadius: 6, color: "#fff", fontSize: big ? 14 : 12, fontWeight: active ? 700 : 400,
                background: active ? c : "rgba(255,255,255,0.05)",
                border: active ? "1px solid " + c : "1px solid transparent",
                boxShadow: focused ? "0 0 0 2px #fff, 0 0 8px 1px " + c : "none",
                transform: focused ? "scale(1.02)" : "scale(1)",
                transition: "box-shadow .08s ease, transform .08s ease",
                opacity: disabled ? 0.5 : 1, zIndex: focused ? 1 : 0,
            }}
        >
            {children}
        </Btn>
    );
}

// Self-focused CardBtn for isolated actions.
export function ActionCard({ color, active, disabled, center, big, onClick, children }: any) {
    const [focused, setFocused] = useState(false);
    return (
        <CardBtn
            color={color}
            active={active}
            disabled={disabled}
            focused={focused}
            center={center !== false}
            big={big}
            onClick={onClick}
            onFocus={() => setFocused(true)}
            onBlur={() => setFocused(false)}
        >
            {children}
        </CardBtn>
    );
}

// Small square icon button (toolbar) with the same halo treatment.
export function IconBtn({ color, disabled, onClick, children }: any) {
    const [focused, setFocused] = useState(false);
    const c = color || ACCENT;
    return (
        <Btn
            disabled={disabled}
            onClick={onClick}
            onFocus={() => setFocused(true)}
            onBlur={() => setFocused(false)}
            style={{
                width: 48, minWidth: 48, padding: 0, margin: 0, minHeight: 40, boxSizing: "border-box",
                display: "flex", alignItems: "center", justifyContent: "center",
                borderRadius: 6, color: "#fff",
                background: focused ? c : "rgba(255,255,255,0.06)",
                boxShadow: focused ? "0 0 0 2px #fff, 0 0 8px 1px " + c : "none",
                transition: "background .08s ease, box-shadow .08s ease",
                opacity: disabled ? 0.5 : 1,
            }}
        >
            {children}
        </Btn>
    );
}
