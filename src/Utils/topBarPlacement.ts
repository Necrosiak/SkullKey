// Steam controls can contain several SVGs (controller + battery). Never use
// their SVG count to identify the outer navigation row.
function visibleSlots(row: HTMLElement, doc: Document): HTMLElement[] {
    const win = doc.defaultView;
    if (!win) return [];
    const style = win.getComputedStyle(row);
    if (style.display !== "flex" || !["row", "row-reverse"].includes(style.flexDirection)) return [];
    const slots = (Array.from(row.children) as HTMLElement[]).filter(child => {
        if (child.hasAttribute("data-sk-topbar")) return false;
        const b = child.getBoundingClientRect();
        return b.top >= 0 && b.top < 45 && b.width >= 20 && b.width <= 160
            && b.height >= 16 && b.height <= 60 && b.left > win.innerWidth / 2;
    }).sort((a, b) => a.getBoundingClientRect().left - b.getBoundingClientRect().left);
    // Separate, non-overlapping control slots, not layers inside one icon.
    if (slots.length < 3 || slots.some((slot, i) => i > 0
        && slot.getBoundingClientRect().left < slots[i - 1].getBoundingClientRect().right - 1)) return [];
    return slots;
}

export function topBarHolder(doc: Document): HTMLElement | null {
    const win = doc.defaultView;
    if (!win) return null;
    const existing = doc.querySelector("[data-sk-topbar]") as HTMLElement | null;
    if (existing?.isConnected && existing.parentElement
        && visibleSlots(existing.parentElement, doc).length) return existing;
    // Also repair a stale holder left inside a Steam control by an older build.
    existing?.remove();
    const icons = Array.from(doc.querySelectorAll("svg")).filter(icon => {
        const b = icon.getBoundingClientRect();
        return b.top >= 0 && b.top < 45 && b.width >= 14 && b.height >= 14
            && b.left > win.innerWidth / 2;
    }).sort((a, b) => a.getBoundingClientRect().left - b.getBoundingClientRect().left);
    for (const icon of icons) {
        let row = icon.parentElement;
        for (let depth = 0; row && depth < 8; depth++) {
            const slots = visibleSlots(row, doc);
            if (!slots.length) { row = row.parentElement; continue; }
            const holder = doc.createElement("div");
            holder.setAttribute("data-sk-topbar", "");
            holder.style.cssText = "display:flex;flex:0 0 40px;width:40px;height:40px;box-sizing:border-box;align-items:center;justify-content:center;align-self:center;cursor:pointer";
            row.insertBefore(holder, slots[0]);
            return holder;
        }
    }
    // An unknown Steam layout is safer without an indicator than with an
    // indicator injected into a controller/battery control.
    return null;
}
