import type { Citation } from "@/types/citation";

const EVIDENCE_MARKER_SPLIT_RE =
  /(\[E[1-9]\d*(?:(?::\s*|\|\s*quote\s*=\s*)"[^"\]]*")?\])/gi;
const EVIDENCE_MARKER_TOKEN_RE =
  /^\[E([1-9]\d*)(?:(?::\s*|\|\s*quote\s*=\s*)"([^"\]]*)")?\]$/i;

export function displayNumberFromEvidenceId(
  evidenceId: string | null | undefined
): number | null {
  if (!evidenceId) return null;
  const match = /^E([1-9]\d*)$/i.exec(evidenceId.trim());
  if (!match) return null;
  return Number.parseInt(match[1], 10);
}

export function citationKey(citation: {
  id?: string;
  evidenceId?: string | null;
  quote?: string | null;
  chunk_id?: string | null;
}): string {
  const base = citation.chunk_id || citation.id || citation.evidenceId || "";
  const quote = citation.quote?.trim();
  return quote ? `${base}::${quote}` : base;
}

export function citationsMatch(
  left: { id?: string; evidenceId?: string | null; quote?: string | null; chunk_id?: string | null } | null | undefined,
  right: { id?: string; evidenceId?: string | null; quote?: string | null; chunk_id?: string | null } | null | undefined
): boolean {
  if (!left || !right) return false;
  return citationKey(left) === citationKey(right);
}

export function openCitationPayload(
  citation: Citation,
  quote?: string | null
): Citation {
  const cleanedQuote = quote?.trim() || citation.quote?.trim() || null;
  return {
    ...citation,
    quote: cleanedQuote,
    id: citationKey({ ...citation, quote: cleanedQuote }),
  };
}

/** Hold back a trailing unclosed '[' so partial [E / [E1:" is never rendered. */
export function incompleteBracketLength(value: string): number {
  const last = value.lastIndexOf("[");
  if (last === -1) return 0;
  const rest = value.slice(last);
  if (rest.includes("]")) return 0;
  return rest.length;
}

export function parseEvidenceMarker(
  token: string
): { evidenceId: string; quote: string | null } | null {
  const match = EVIDENCE_MARKER_TOKEN_RE.exec(token.trim());
  if (!match) return null;
  const quote = (match[2] || "").trim();
  return {
    evidenceId: `E${match[1]}`,
    quote: quote.length > 0 ? quote : null,
  };
}

export function splitEvidenceMarkers(
  value: string
): Array<{ type: "text"; value: string } | { type: "citation"; evidenceId: string; quote: string | null }> {
  const parts = value.split(EVIDENCE_MARKER_SPLIT_RE);
  const nodes: Array<
    { type: "text"; value: string } | { type: "citation"; evidenceId: string; quote: string | null }
  > = [];
  for (const part of parts) {
    if (!part) continue;
    const parsed = parseEvidenceMarker(part);
    if (parsed) {
      nodes.push({ type: "citation", ...parsed });
    } else {
      nodes.push({ type: "text", value: part });
    }
  }
  return nodes;
}

export function toDisplayCitationText(content: string): string {
  return content.replace(
    /\[E([1-9]\d*)(?:(?::\s*|\|\s*quote\s*=\s*)"[^"\]]*")?\]/gi,
    "[$1]"
  );
}

export function quotesByEvidenceId(content: string): Map<string, string[]> {
  const found = new Map<string, string[]>();
  for (const part of splitEvidenceMarkers(content)) {
    if (part.type !== "citation" || !part.quote) continue;
    const key = part.evidenceId.toUpperCase();
    const list = found.get(key) || [];
    list.push(part.quote);
    found.set(key, list);
  }
  return found;
}

/** Attach quotes from the answer onto retrieved citations. Unused sources stay quote-less. */
export function withAnswerQuotes<T extends { evidenceId?: string | null; quote?: string | null }>(
  citations: T[] | undefined,
  content: string
): T[] {
  const quotes = quotesByEvidenceId(content);
  return (citations || []).map((citation) => {
    const key = (citation.evidenceId || "").toUpperCase();
    const used = quotes.get(key);
    if (citation.quote && citation.quote.trim()) {
      return citation;
    }
    if (!used?.length) {
      return { ...citation, quote: citation.quote ?? null };
    }
    return { ...citation, quote: used[0] };
  });
}

export function usedEvidenceIds(content: string): string[] {
  const ids: string[] = [];
  const seen = new Set<string>();
  for (const part of splitEvidenceMarkers(content)) {
    if (part.type !== "citation") continue;
    const key = part.evidenceId.toUpperCase();
    if (seen.has(key)) continue;
    seen.add(key);
    ids.push(key);
  }
  return ids;
}

/** Citations the answer actually used, in first-appearance order. */
export function usedCitations<T extends { evidenceId?: string | null; quote?: string | null }>(
  citations: T[] | undefined,
  content: string
): T[] {
  const quoted = withAnswerQuotes(citations, content);
  const byId = new Map<string, T>();
  for (const citation of quoted) {
    const key = (citation.evidenceId || "").toUpperCase();
    if (!key || byId.has(key)) continue;
    byId.set(key, citation);
  }
  const out: T[] = [];
  for (const id of usedEvidenceIds(content)) {
    const item = byId.get(id);
    if (item) out.push(item);
  }
  return out;
}

/**
 * Citations referenced in the answer, with degraded stubs when metadata is missing.
 * Prevents silent UI dropout for valid [E#] markers.
 */
export function usedCitationsWithFallback(
  citations: Citation[] | undefined,
  content: string
): Citation[] {
  const resolved = usedCitations(citations, content);
  const byId = new Map(
    resolved.map((item) => [(item.evidenceId || "").toUpperCase(), item])
  );
  const out: Citation[] = [];
  for (const id of usedEvidenceIds(content)) {
    const existing = byId.get(id);
    if (existing) {
      out.push(existing);
      continue;
    }
    const displayNumber = displayNumberFromEvidenceId(id);
    if (displayNumber === null) continue;
    out.push({
      id: `orphan-${id}`,
      documentName: "Source",
      pageNumber: null,
      evidenceId: id.toUpperCase(),
      displayNumber,
      quoteMappingStatus: "unresolved",
      quoteHighlightAvailable: false,
      uiStatus: "citation_dropped",
    });
  }
  return out;
}
