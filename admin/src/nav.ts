/** Tab names, shared by the shell (App) and pages that send the user elsewhere. */
export type Tab = "home" | "connections" | "clients" | "advanced";

/** Switch tabs from anywhere, e.g. the Home checklist or an empty state. */
export function goTo(tab: Tab) {
  window.location.hash = tab;
}
