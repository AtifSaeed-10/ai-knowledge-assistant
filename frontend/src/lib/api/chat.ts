import { Citation } from "@/types";
import { ProductMode } from "@/types/mode";
import { API_CONFIG } from "./client";
import {
  displayNumberFromEvidenceId,
  incompleteBracketLength,
} from "@/lib/citations/markers";
import type { EvidenceRegion } from "@/types/citation";

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
  quotes?: string[] | null;
  quote_mapping_status?: string | null;
  quote_highlight_available?: boolean | null;
  quote_regions?: EvidenceRegion[] | null;
}

const CITATIONS_START = "__CITATIONS__";
const CITATIONS_FINAL_START = "__CITATIONS_FINAL__";
const CITATIONS_END = "__END_CITATIONS__";

export function mapSourceToCitation(src: ApiSource, idx: number): Citation {
  const rawPage = src.page ?? src.page_number;
  const pageNumber =
    typeof rawPage === "number" && Number.isFinite(rawPage) && rawPage >= 1
      ? Math.floor(rawPage)
      : null;
  const evidenceId = src.evidence_id || src.evidenceId || null;
  const displayNumber = displayNumberFromEvidenceId(evidenceId);
  const quotes = Array.isArray(src.quotes)
    ? src.quotes.filter((item): item is string => typeof item === "string" && item.trim().length > 0)
    : [];
  const quote =
    typeof src.quote === "string" && src.quote.trim()
      ? src.quote.trim()
      : quotes[0] ?? null;

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
    quote,
    quotes: quotes.length > 0 ? quotes : quote ? [quote] : [],
    quoteMappingStatus: src.quote_mapping_status ?? null,
    quoteHighlightAvailable: src.quote_highlight_available === true,
    quoteRegions: Array.isArray(src.quote_regions)
      ? src.quote_regions.filter(
          (region): region is EvidenceRegion =>
            Boolean(region && typeof region === "object" && typeof region.page === "number")
        )
      : [],
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

function tryParseCitations(payload: string): Citation[] {
  try {
    const raw = JSON.parse(payload) as ApiSource[];
    return raw.map(mapSourceToCitation);
  } catch {
    return [];
  }
}

function stripControlMarkers(buffer: string): {
  buffer: string;
  citations: Citation[] | null;
  marker: "initial" | "final" | null;
} {
  for (const [start, kind] of [
    [CITATIONS_FINAL_START, "final"],
    [CITATIONS_START, "initial"],
  ] as const) {
    const begin = buffer.indexOf(start);
    const end = buffer.indexOf(CITATIONS_END);
    if (begin !== -1 && end !== -1 && end > begin) {
      const payload = buffer.slice(begin + start.length, end);
      const citations = tryParseCitations(payload);
      const next = buffer.slice(0, begin) + buffer.slice(end + CITATIONS_END.length);
      return { buffer: next, citations, marker: kind };
    }
  }
  return { buffer, citations: null, marker: null };
}

export const chatApi = {
  /**
   * POST /chat/stream
   * The server sends `__CITATIONS__[...]__END_CITATIONS__` first, then answer tokens,
   * then optional `__CITATIONS_FINAL__[...]__END_CITATIONS__` with validated citations.
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

      while (true) {
        const parsed = stripControlMarkers(buffer);
        buffer = parsed.buffer;
        if (!parsed.citations) break;
        if (parsed.marker === "initial" && !citationsSent) {
          onCitations(parsed.citations);
          citationsSent = true;
        } else if (parsed.marker === "final") {
          onCitations(parsed.citations);
          citationsSent = true;
        }
      }

      let emitUpTo = buffer.length;
      if (!citationsSent) {
        const start = buffer.indexOf(CITATIONS_START);
        emitUpTo =
          start !== -1
            ? start
            : buffer.length - partialMarkerLength(buffer, CITATIONS_START);
      } else {
        const finalStart = buffer.indexOf(CITATIONS_FINAL_START);
        if (finalStart !== -1) {
          emitUpTo = finalStart;
        } else {
          emitUpTo =
            buffer.length - partialMarkerLength(buffer, CITATIONS_FINAL_START);
        }
        emitUpTo = Math.min(emitUpTo, buffer.length - incompleteBracketLength(buffer));
      }

      if (emitUpTo > 0) {
        onChunk(buffer.slice(0, emitUpTo));
        buffer = buffer.slice(emitUpTo);
      }
    }

    while (true) {
      const parsed = stripControlMarkers(buffer);
      buffer = parsed.buffer;
      if (!parsed.citations) break;
      if (parsed.marker === "final" || (parsed.marker === "initial" && !citationsSent)) {
        onCitations(parsed.citations);
        citationsSent = true;
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
