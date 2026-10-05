export type PanelPreferences = {
  rail: "expanded" | "collapsed" | "hidden";
  railWidth: number;
  inspectorOpen: boolean;
  inspectorWidth: number;
};
export type EvidenceSelection = { turnId: string; citationIndex: number };
export type PanelIdentityScope = { issuer: string; subject: string };
export const DEFAULT_PANEL_PREFERENCES: PanelPreferences = {
  rail: "expanded",
  railWidth: 252,
  inspectorOpen: true,
  inspectorWidth: 376,
};
const namespace = "knora:conversation-panels:v1:";
export function panelPreferenceKey(
  scope: PanelIdentityScope | undefined,
  workspaceId: string,
): string | null {
  if (
    !scope ||
    !scope.subject.trim() ||
    scope.subject.length > 512 ||
    !workspaceId
  )
    return null;
  try {
    const issuer = new URL(scope.issuer);
    if (
      !["https:", "http:"].includes(issuer.protocol) ||
      issuer.username ||
      issuer.password ||
      issuer.search ||
      issuer.hash
    )
      return null;
    return `${namespace}${encodeURIComponent(scope.issuer)}:${encodeURIComponent(scope.subject)}:${encodeURIComponent(workspaceId)}`;
  } catch {
    return null;
  }
}
export function readPanelPreferences(key: string | null): PanelPreferences {
  if (!key) return { ...DEFAULT_PANEL_PREFERENCES };
  try {
    const value = JSON.parse(sessionStorage.getItem(key) ?? "null");
    if (
      value?.version !== 1 ||
      !["expanded", "collapsed", "hidden"].includes(value.rail) ||
      typeof value.inspectorOpen !== "boolean" ||
      !Number.isFinite(value.railWidth) ||
      !Number.isFinite(value.inspectorWidth)
    )
      return { ...DEFAULT_PANEL_PREFERENCES };
    return {
      rail: value.rail,
      railWidth: Math.max(200, Math.min(400, value.railWidth)),
      inspectorOpen: value.inspectorOpen,
      inspectorWidth: Math.max(280, Math.min(520, value.inspectorWidth)),
    };
  } catch {
    return { ...DEFAULT_PANEL_PREFERENCES };
  }
}
export function writePanelPreferences(
  key: string | null,
  preferences: PanelPreferences,
) {
  if (!key) return;
  try {
    sessionStorage.setItem(key, JSON.stringify({ version: 1, ...preferences }));
  } catch {
    /* Storage is optional. */
  }
}
/** I3 can clear only this feature's preferences on sign-out. */
export function clearConversationPanelPreferences(storage?: Storage) {
  try {
    const target = storage ?? sessionStorage;
    const keys = Array.from({ length: target.length }, (_, index) =>
      target.key(index),
    );
    for (const key of keys)
      if (key?.startsWith(namespace)) target.removeItem(key);
  } catch {
    /* Storage is optional. */
  }
}
