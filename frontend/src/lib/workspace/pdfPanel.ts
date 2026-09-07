/**
 * Pure rules for the document preview pane.
 *
 * The pane is a frontend-only concern: the API still serves the same file
 * and citation payload it always did.
 */

export const PDF_PANEL_MIN_WIDTH = 320;
export const PDF_PANEL_MAX_WIDTH = 720;
export const PDF_PANEL_DEFAULT_WIDTH = 460;
export const PDF_PANEL_MIN_CHAT_WIDTH = 380;

export function clampPdfPanelWidth(
  width: number,
  maxAvailable: number = PDF_PANEL_MAX_WIDTH
): number {
  const cap = Math.max(
    PDF_PANEL_MIN_WIDTH,
    Math.min(PDF_PANEL_MAX_WIDTH, Math.floor(maxAvailable))
  );
  if (!Number.isFinite(width)) return Math.min(PDF_PANEL_DEFAULT_WIDTH, cap);
  return Math.min(cap, Math.max(PDF_PANEL_MIN_WIDTH, Math.round(width)));
}

/** Leave enough room for the chat column when the workspace is narrow. */
export function maxPdfWidthForWorkspace(workspaceWidth: number): number {
  if (!Number.isFinite(workspaceWidth) || workspaceWidth <= 0) {
    return PDF_PANEL_MAX_WIDTH;
  }
  return Math.max(
    PDF_PANEL_MIN_WIDTH,
    workspaceWidth - PDF_PANEL_MIN_CHAT_WIDTH
  );
}

export function resolvePreviewDocument<T extends { id: string }>(options: {
  documents: T[];
  selectedDocumentId: string | null | undefined;
  citationDocumentId?: string | null;
  previewDocumentId?: string | null;
}): T | null {
  const { documents, selectedDocumentId, citationDocumentId, previewDocumentId } =
    options;
  for (const id of [citationDocumentId, previewDocumentId, selectedDocumentId]) {
    if (!id) continue;
    const match = documents.find((doc) => doc.id === id);
    if (match) return match;
  }
  return documents[0] ?? null;
}

/**
 * Phones cannot keep chat and a PDF side by side. The overlay only appears
 * when the reader asked for the file (citation click or Show PDF).
 */
export function shouldShowMobileOverlay(options: {
  isOpen: boolean;
  pinned: boolean;
  hasCitation: boolean;
}): boolean {
  if (!options.isOpen) return false;
  return options.pinned || options.hasCitation;
}

/** Jump the already-open preview to the first source of a new answer. */
export function shouldFollowAnswerCitation(options: {
  isOpen: boolean;
  citationCount: number;
}): boolean {
  return options.isOpen && options.citationCount > 0;
}
