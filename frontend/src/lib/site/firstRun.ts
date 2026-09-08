/** Kept from the earlier one-shot upload tip so existing dismissals still count. */
const WORKSPACE_TOUR_KEY = "docusage_seen_upload_guide";

function canUseStorage(): boolean {
  return typeof window !== "undefined";
}

export function hasSeenWorkspaceTour(): boolean {
  if (!canUseStorage()) return true;
  try {
    return window.localStorage.getItem(WORKSPACE_TOUR_KEY) === "true";
  } catch {
    return true;
  }
}

export function markWorkspaceTourSeen(): void {
  if (!canUseStorage()) return;
  try {
    window.localStorage.setItem(WORKSPACE_TOUR_KEY, "true");
  } catch {
    /* private mode — the tour may appear again this visit */
  }
}
