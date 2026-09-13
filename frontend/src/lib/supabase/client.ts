import {
  createClient,
  type Session,
  type SupabaseClient,
} from "@supabase/supabase-js";

/**
 * Supabase browser client for Google sign-in.
 *
 * Absent env vars are a supported state: the app runs guest-only and the
 * signup modal explains that sign-in is not enabled yet.
 */
const SUPABASE_URL = process.env.NEXT_PUBLIC_SUPABASE_URL || "";
const SUPABASE_ANON_KEY = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY || "";

let client: SupabaseClient | null = null;

export function isSupabaseConfigured(): boolean {
  return Boolean(SUPABASE_URL && SUPABASE_ANON_KEY);
}

export function getSupabaseClient(): SupabaseClient | null {
  if (!isSupabaseConfigured()) return null;
  if (!client) {
    client = createClient(SUPABASE_URL, SUPABASE_ANON_KEY, {
      auth: {
        persistSession: true,
        autoRefreshToken: true,
        detectSessionInUrl: true,
      },
    });
  }
  return client;
}

/** Redirect to Google. The app reloads with a session in the URL fragment. */
export async function signInWithGoogle(redirectTo?: string): Promise<void> {
  const supabase = getSupabaseClient();
  if (!supabase) {
    throw new Error("Sign-in is not configured on this deployment.");
  }

  const { error } = await supabase.auth.signInWithOAuth({
    provider: "google",
    options: {
      redirectTo: redirectTo || window.location.origin,
    },
  });

  if (error) throw new Error(error.message);
}

export async function signOut(): Promise<void> {
  await getSupabaseClient()?.auth.signOut();
}

export async function getCurrentSession(): Promise<Session | null> {
  const supabase = getSupabaseClient();
  if (!supabase) return null;
  const { data } = await supabase.auth.getSession();
  return data.session ?? null;
}

/** Subscribe to sign-in/sign-out/token-refresh. Returns an unsubscribe fn. */
export function onAuthStateChange(
  handler: (session: Session | null) => void
): () => void {
  const supabase = getSupabaseClient();
  if (!supabase) return () => {};

  const { data } = supabase.auth.onAuthStateChange((_event, session) => {
    handler(session);
  });

  return () => data.subscription.unsubscribe();
}
