/**
 * Chunk metadata stores the PDF as it sits on disk — `{document_id}.pdf` —
 * so a citation can arrive carrying an id instead of a readable title.
 * The library already knows the uploaded name, so prefer that.
 */

const STORED_PDF_RE =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\.pdf$/i;

export function isStoredFileName(name?: string | null): boolean {
  return STORED_PDF_RE.test((name || "").trim());
}

export function resolveCitationDocumentName(
  citation: { documentId?: string | null; documentName?: string | null },
  documents: Array<{ id: string; name: string }>,
  fallback = "Source"
): string {
  const fromLibrary = citation.documentId
    ? documents.find((doc) => doc.id === citation.documentId)?.name
    : undefined;
  if (fromLibrary) return fromLibrary;

  const given = (citation.documentName || "").trim();
  if (!given || isStoredFileName(given)) return fallback;
  return given;
}
