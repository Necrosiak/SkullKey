// Discs & Installers — steps of the "Add a game" dialog, as a pure state
// machine so the order of steps is testable without Steam.

export type SourceKind = "image" | "optical" | "installer" | "ready" | "folder";

export interface Candidate { path: string; score: number; default_ok: boolean; }

export interface FlowState {
    step: "source" | "title" | "drive" | "preparing" | "installer-ready" | "installer-running"
        | "exe-loading" | "exe-choose" | "exe-manual" | "done" | "cancelled" | "error";
    kind?: SourceKind;
    path?: string;
    parts?: string[];
    title?: string;
    root?: string;
    candidates?: Candidate[];
    exe?: string;
    message?: string;
}

export type FlowEvent =
    | { type: "source"; kind: SourceKind; path: string; parts?: string[]; label?: string }
    | { type: "title"; title: string }
    | { type: "drive"; root: string }
    | { type: "prepared"; stage: string }
    | { type: "installerStarted" }
    | { type: "installerClosed" }
    | { type: "candidates"; list: Candidate[] }
    | { type: "exe"; path: string }
    | { type: "error"; message: string }
    | { type: "cancel" };

const FINAL = new Set(["done", "cancelled", "error"]);

export function initialState(): FlowState {
    return { step: "source" };
}

export function nextStep(state: FlowState, event: FlowEvent): FlowState {
    if (FINAL.has(state.step)) return state;
    if (event.type === "cancel") return { ...state, step: "cancelled" };
    if (event.type === "error") return { ...state, step: "error", message: event.message };
    switch (event.type) {
        case "source":
            if (state.step !== "source") return state;
            return { ...state, step: "title", kind: event.kind, path: event.path,
                     parts: event.parts && event.parts.length ? event.parts : [event.path],
                     title: event.label || "" };
        case "title":
            if (state.step !== "title" || !event.title.trim()) return state;
            return { ...state, step: "drive", title: event.title.trim() };
        case "drive":
            return state.step === "drive" ? { ...state, step: "preparing", root: event.root } : state;
        case "prepared":
            if (state.step !== "preparing") return state;
            return { ...state, step: event.stage === "needs-installer" ? "installer-ready" : "exe-loading" };
        case "installerStarted":
            return state.step === "installer-ready" ? { ...state, step: "installer-running" } : state;
        case "installerClosed":
            return state.step === "installer-running" ? { ...state, step: "exe-loading" } : state;
        case "candidates":
            if (state.step !== "exe-loading") return state;
            return { ...state, step: event.list.length ? "exe-choose" : "exe-manual", candidates: event.list };
        case "exe":
            if (state.step !== "exe-choose" && state.step !== "exe-manual") return state;
            return { ...state, step: "done", exe: event.path };
    }
    return state;
}

// Pre-selected candidate: the best one that may be a default.
export function defaultCandidate(list: Candidate[]): Candidate | undefined {
    return list.find(c => c.default_ok) ?? undefined;
}
