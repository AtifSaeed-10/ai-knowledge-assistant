import { Citation } from "@/types";
import { ProductMode } from "@/types/mode";
import { API_CONFIG } from "./client";
import {
  displayNumberFromEvidenceId,
  incompleteBracketLength,
} from "@/lib/citations/markers";

interface ApiSource {
  document_id?: string;
  filename?: string;
  page?: number | null;
  page_number?: number | null;
  chunk_id?: string;
  relevance?: number;
  snippet?: string;
  text?: string;
  evidence_id?: string;
  evidenceId?: string;
  quote?: string | null;
}

const CITATIONS_START = "__CITATIONS__";
const CITATIONS_END = "__END_CITATIONS__";

export function mapSourceToCitation(src: ApiSource, idx: number): Citation {
  const rawPage = src.page ?? src.page_number;
  const pageNumber =
    typeof rawPage === "number" && Number.isFinite(rawPage) && rawPage >= 1
      ? Math.floor(rawPage)
      : null;
  const evidenceId = src.evidence_id || src.evidenceId || null;
  const displayNumber = displayNumberFromEvidenceId(evidenceId);

  return {
    id: src.chunk_id || `cit-${Date.now()}-${idx}`,
    documentName: src.filename || "Unknown document",
    pageNumber,
    snippet: src.snippet ?? src.text,
    relevance: src.relevance ?? null,
    chunk_id: src.chunk_id ?? null,
    documentId: src.document_id ?? null,
    evidenceId,
    displayNumber,
    quote: typeof src.quote === "string" && src.quote.trim() ? src.quote.trim() : null,
  };
}

/**
 * Length of the longest suffix of `value` that is also a prefix of `marker`.
 * Used to hold back text that might turn out to be a split control marker.
 */
function partialMarkerLength(value: string, marker: string): number {
  const max = Math.min(value.length, marker.length - 1);
  for (let size = max; size > 0; size -= 1) {
    if (value.endsWith(marker.slice(0, size))) return size;
  }
  return 0;
}

export const chatApi = {
  /**
   * POST /chat/stream
   * The server sends `__CITATIONS__[...]__END_CITATIONS__` first, then answer tokens.
   */
  async streamMessage(
    content: string,
    documentIds: string[],
    conversationId: string,
    onChunk: (chunk: string) => void,
    onCitations: (citations: Citation[]) => void,
    mode: ProductMode = "normal",
    signal?: AbortSignal,
    regenerate: boolean = false
  ): Promise<void> {
    const response = await fetch(`${API_CONFIG.baseUrl}/chat/stream`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        question: content,
        conversation_id: conversationId,
        document_ids: documentIds,
        mode,
        regenerate,
      }),
      signal,
    });

    if (!response.ok) {
      throw new Error(
        response.status >= 500
          ? "The server could not generate an answer. Please try again."
          : `The request was rejected (${response.status}).`
      );
    }

    const reader = response.body?.getReader();
    if (!reader) {
      throw new Error("Streaming is not supported by this browser.");
    }

    const decoder = new TextDecoder();
    let buffer = "";
    let citationsSent = false;

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });

      if (!citationsSent) {
        const start = buffer.indexOf(CITATIONS_START);
        const end = buffer.indexOf(CITATIONS_END);

        if (start !== -1 && end !== -1 && end > start) {
          const payload = buffer.slice(start + CITATIONS_START.length, end);

          try {
            const raw = JSON.parse(payload) as ApiSource[];
            onCitations(raw.map(mapSourceToCitation));
          } catch {
            onCitations([]);
          }

          citationsSent = true;
          buffer = buffer.slice(0, start) + buffer.slice(end + CITATIONS_END.length);
        }
      }

      // Never emit text that might be the beginning of a control marker
      // or an incomplete [E1] citation token.
      let emitUpTo = buffer.length;
      if (!citationsSent) {
        const start = buffer.indexOf(CITATIONS_START);
        emitUpTo =
          start !== -1
            ? start
            : buffer.length - partialMarkerLength(buffer, CITATIONS_START);
      } else {
        emitUpTo = buffer.length - incompleteBracketLength(buffer);
      }

      if (emitUpTo > 0) {
        onChunk(buffer.slice(0, emitUpTo));
        buffer = buffer.slice(emitUpTo);
      }
    }

    if (buffer.length > 0) {
      const hold = citationsSent ? incompleteBracketLength(buffer) : 0;
      if (hold < buffer.length) {
        onChunk(buffer.slice(0, buffer.length - hold));
      }
    }

    if (!citationsSent) {
      onCitations([]);
    }
  },
};
