import { DialogButton, Focusable, Navigation, ServerAPI } from "decky-frontend-lib";
import { VFC, useEffect, useState } from "react";
import { storeTheme } from "./Styled";
import { t } from "../i18n";

// Store tab -> key used by the free-games backend.
const STORE_OF: Record<string, string> = {
    EpicActions: "epic", GOGActions: "gog", AmazonActions: "amazon", UbisoftActions: "ubisoft",
    BattleNetActions: "battlenet", EAActions: "ea",
};

interface Offer { id: string; store: string; title: string; now: boolean; start: string; end: string; url: string; image: string }

// "Free this week" strip at the top of a store's grid: the store's current
// giveaways (and the next ones), each with a Claim button that opens the
// store page in Steam's browser.
export const FreeBanner: VFC<{ serverAPI: ServerAPI; actionSet: string }> = ({ serverAPI, actionSet }) => {
    const store = STORE_OF[actionSet];
    const [offers, setOffers] = useState<Offer[]>([]);
    // Steam darkens the text of a focused DialogButton for its own white
    // highlight; with our dark card that hid the title. Track focus ourselves.
    const [focus, setFocus] = useState<string | null>(null);
    useEffect(() => {
        if (!store) return;
        serverAPI.callPluginMethod<{}, { offers: Offer[] }>("free_games_list", {})
            .then(r => r.success && setOffers((r.result?.offers || []).filter(o => o.store === store)));
    }, [store]);
    if (!store || !offers.length) return null;
    const color = storeTheme(actionSet).color;
    const now = offers.filter(o => o.now), soon = offers.filter(o => !o.now);
    return (
        <div style={{ marginTop: 10, padding: "8px 12px", borderRadius: 6, background: "rgba(255,255,255,0.04)",
                      borderLeft: `3px solid ${color}` }}>
            <div style={{ fontSize: 12, fontWeight: 700, textTransform: "uppercase", letterSpacing: ".5px", color, marginBottom: 6 }}>
                🎁 {t("free_this_week")}
            </div>
            <Focusable flow-children="horizontal" style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
                {now.map(o => (
                    <DialogButton key={o.id} noFocusRing
                        onGamepadFocus={() => setFocus(o.id)} onGamepadBlur={() => setFocus(f => f === o.id ? null : f)}
                        style={{ minWidth: 0, width: "auto", padding: 0, display: "flex", alignItems: "center", gap: 10,
                                 background: focus === o.id ? color : "rgba(255,255,255,0.06)", color: "#fff",
                                 borderRadius: 6, overflow: "hidden", height: 56,
                                 boxShadow: focus === o.id ? `0 0 0 2px #fff, 0 0 10px 2px ${color}` : "none",
                                 transform: focus === o.id ? "scale(1.03)" : "none", transition: "transform .1s, box-shadow .1s" }}
                        onClick={() => { Navigation.CloseSideMenus(); Navigation.NavigateToExternalWeb(o.url); }}>
                        {o.image && <img src={o.image} style={{ height: 56, width: 100, objectFit: "cover" }} />}
                        <span style={{ display: "flex", flexDirection: "column", alignItems: "flex-start", paddingRight: 14, lineHeight: 1.3 }}>
                            <span style={{ fontSize: 13, fontWeight: 600 }}>{o.title}</span>
                            <span style={{ fontSize: 11, opacity: 0.7 }}>
                                {t("free_claim")}{o.end ? " · " + t("free_until", { date: o.end }) : ""}
                            </span>
                        </span>
                    </DialogButton>
                ))}
            </Focusable>
            {!!soon.length && (
                <div style={{ fontSize: 11, opacity: 0.7, marginTop: 6 }}>
                    {t("free_soon")} : {soon.map(o => `${o.title} (${t("free_from", { date: o.start })})`).join(" · ")}
                </div>
            )}
        </div>
    );
};
