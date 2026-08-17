import type { Citation } from './citation';

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
}
