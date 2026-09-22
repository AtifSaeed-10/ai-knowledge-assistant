import type { Citation } from './citation';
import type { ScopeChoice } from '@/lib/workspace/documentScope';

export type MessageRole = 'user' | 'assistant';

/**
 * 'error'   — generation failed; the message body holds a user-safe reason.
 * 'stopped' — the user stopped generation; any partial content is preserved.
 */
export type MessageStatus = 'ok' | 'error' | 'stopped';

export interface Message {
  id: string;
  role: MessageRole;
  content: string;
  timestamp: Date;
  citations?: Citation[];
  status?: MessageStatus;
  /** Local "which PDF?" chips — never persisted. */
  scopeChoices?: ScopeChoice[];
  pendingQuestion?: string;
  /** Shown once, under the answer the reader had to disambiguate. */
  scopeHint?: string;
  /** Live pipeline label while the server is retrieving or searching. */
  streamStatus?: string | null;
}
