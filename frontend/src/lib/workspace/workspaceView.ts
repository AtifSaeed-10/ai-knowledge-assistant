/**
 * When to keep the chat pane instead of the empty upload screen.
 *
 * Chat history is independent of PDFs. Deleting the last file must not hide
 * saved transcripts — the sidebar still lists them, and clicking one needs
 * somewhere to open.
 */
export function shouldShowChatWorkspace(options: {
  documentCount: number;
  conversationCount: number;
  messageCount: number;
  conversationId: string;
}): boolean {
  return (
    options.documentCount > 0 ||
    options.conversationCount > 0 ||
    options.messageCount > 0 ||
    Boolean(options.conversationId)
  );
}

/**
 * Skip a reload only when this chat is already open and its transcript is
 * on screen. An empty pane (or a previous load error) should fetch again,
 * even if the same history row is already highlighted.
 */
export function shouldSkipConversationReload(options: {
  requestedId: string;
  currentId: string;
  conversationError: string | null;
  messageCount: number;
  isSwitching: boolean;
}): boolean {
  if (!options.requestedId) return true;
  if (options.requestedId !== options.currentId) return false;
  if (options.conversationError) return false;
  if (options.isSwitching) return true;
  return options.messageCount > 0;
}
