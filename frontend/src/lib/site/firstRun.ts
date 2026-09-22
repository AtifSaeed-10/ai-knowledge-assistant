/** Browser copy — kept from the earlier one-shot upload tip. */
const LOCAL_TOUR_KEY = "docusage_seen_upload_guide";
/** Follows the Google account across devices via Supabase user_metadata. */
export const ACCOUNT_TOUR_KEY = "docusage_seen_workspace_tour";

function canUseStorage(): boolean {
  return typeof window !== "undefined";
}

export function accountHasSeenWorkspaceTour(
  meta: Record<string, unknown> | null | undefined
): boolean {
  const value = meta?.[ACCOUNT_TOUR_KEY];
  return value === true || value === "true";
}

/**
 * Guest: this browser. Signed-in: this browser OR the account.
 * Either store is enough to skip — we never show the tour twice on purpose.
 */
export function hasSeenWorkspaceTour(accountSeen = false): boolean {
  if (accountSeen) return true;
  if (!canUseStorage()) return true;
  try {
    return window.localStorage.getItem(LOCAL_TOUR_KEY) === "true";
  } catch {
    return true;
  }
}

export function markWorkspaceTourSeen(): void {
  if (!canUseStorage()) return;
  try {
    window.localStorage.setItem(LOCAL_TOUR_KEY, "true");
  } catch {
    /* private mode — the tour may appear again this visit */
  }
}

/** After sign-in, copy the flag so neither store is stale. */
export function tourSeenSync(options: {
  localSeen: boolean;
  accountSeen: boolean;
}): { writeLocal: boolean; writeAccount: boolean } {
  return {
    writeLocal: options.accountSeen && !options.localSeen,
    writeAccount: options.localSeen && !options.accountSeen,
  };
}

export async function persistWorkspaceTourToAccount(): Promise<void> {
  const { getSupabaseClient } = await import("@/lib/supabase/client");
  const supabase = getSupabaseClient();
  if (!supabase) return;
  try {
    const { data } = await supabase.auth.getSession();
    if (!data.session) return;
    await supabase.auth.updateUser({
      data: { [ACCOUNT_TOUR_KEY]: true },
    });
  } catch {
    /* this device still has localStorage */
  }
}

export async function rememberWorkspaceTourSeen(): Promise<void> {
  markWorkspaceTourSeen();
  await persistWorkspaceTourToAccount();
}

export async function syncWorkspaceTourWithAccount(
  meta: Record<string, unknown> | null | undefined
): Promise<void> {
  const plan = tourSeenSync({
    localSeen: hasSeenWorkspaceTour(false),
    accountSeen: accountHasSeenWorkspaceTour(meta),
  });
  if (plan.writeLocal) markWorkspaceTourSeen();
  if (plan.writeAccount) await persistWorkspaceTourToAccount();
}
