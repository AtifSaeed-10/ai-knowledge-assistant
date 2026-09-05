import type { Citation } from "@/types/citation";
import { ProductMode } from "@/types/mode";
import { apiFetch } from "./client";
import {
  displayNumberFromEvidenceId,
  incompleteBracketLength,
} from "@/lib/citations/markers";
import type { EvidenceRegion } from "@/types/citation";

export interface ApiSource {
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
  claim_context?: string | null;
  localization_confidence?: number | null;
  ui_status?: string | null;
  content_type?: string | null;
  evidence_data_available?: boolean | null;
  highlight_available?: boolean | null;
  evidence_state?: string | null;
  citation_eligible?: boolean | null;
}

const CITATIONS_START = "__CITATIONS__";
const CITATIONS_FINAL_START = "__CITATIONS_FINAL__";
const CITATIONS_END = "__END_CITATIONS__";
const ANSWER_FINAL_START = "__ANSWER_FINAL__";
const ANSWER_FINAL_END = "__END_ANSWER_FINAL__";

const FRAME_STARTS = [CITATIONS_FINAL_START, CITATIONS_START, ANSWER_FINAL_START];

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
    claimContext:
      typeof src.claim_context === "string" && src.claim_context.trim()
        ? src.claim_context.trim()
        : null,
    localizationConfidence:
      typeof src.localization_confidence === "number" &&
      Number.isFinite(src.localization_confidence)
        ? src.localization_confidence
        : null,
    uiStatus: typeof src.ui_status === "string" ? src.ui_status : null,
    contentType: typeof src.content_type === "string" ? src.content_type : null,
    evidenceState: typeof src.evidence_state === "string" ? src.evidence_state : null,
    citationEligible:
      typeof src.citation_eligible === "boolean" ? src.citation_eligible : null,
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

function tryParseAnswer(payload: string): string | null {
  try {
    const raw = JSON.parse(payload);
    return typeof raw === "string" ? raw : null;
  } catch {
    return null;
  }
}

type ControlEvent =
  | { kind: "citations"; citations: Citation[]; final: boolean }
  | { kind: "answer"; answer: string };

/** Remove the first complete control frame from the buffer, if there is one. */
function takeControlFrame(buffer: string): {
  buffer: string;
  event: ControlEvent | null;
  consumed: boolean;
} {
  const answerBegin = buffer.indexOf(ANSWER_FINAL_START);
  if (answerBegin !== -1) {
    const from = answerBegin + ANSWER_FINAL_START.length;
    const answerEnd = buffer.indexOf(ANSWER_FINAL_END, from);
    if (answerEnd !== -1) {
      const answer = tryParseAnswer(buffer.slice(from, answerEnd));
      const next =
        buffer.slice(0, answerBegin) + buffer.slice(answerEnd + ANSWER_FINAL_END.length);
      return {
        buffer: next,
        event: answer === null ? null : { kind: "answer", answer },
        consumed: true,
      };
    }
  }

  for (const [start, final] of [
    [CITATIONS_FINAL_START, true],
    [CITATIONS_START, false],
  ] as const) {
    const begin = buffer.indexOf(start);
    const end = buffer.indexOf(CITATIONS_END);
    if (begin !== -1 && end !== -1 && end > begin) {
      const citations = tryParseCitations(buffer.slice(begin + start.length, end));
      const next = buffer.slice(0, begin) + buffer.slice(end + CITATIONS_END.length);
      return { buffer: next, event: { kind: "citations", citations, final }, consumed: true };
    }
  }

  return { buffer, event: null, consumed: false };
}

export interface StreamHandlers {
  onChunk: (chunk: string) => void;
  onCitations: (citations: Citation[]) => void;
  /** Server-validated answer that supersedes every token streamed so far. */
  onFinalAnswer?: (answer: string) => void;
}

/**
 * Incremental reader for the /chat/stream protocol.
 *
 * Answer tokens are emitted as they arrive, minus any text that could still
 * turn out to be a split control marker.
 */
export function createStreamParser(handlers: StreamHandlers) {
  let buffer = "";
  let citationsSent = false;
  let answerReplaced = false;

  const drainFrames = () => {
    while (true) {
      const parsed = takeControlFrame(buffer);
      buffer = parsed.buffer;
      if (!parsed.consumed) break;
      if (!parsed.event) continue;
      if (parsed.event.kind === "answer") {
        answerReplaced = true;
        handlers.onFinalAnswer?.(parsed.event.answer);
        continue;
      }
      if (parsed.event.final || !citationsSent) {
        handlers.onCitations(parsed.event.citations);
        citationsSent = true;
      }
    }
  };

  /** How much of the buffer is safe to show as answer text right now. */
  const emitLimit = () => {
    // The replacement answer supersedes the draft, including any tokens that
    // arrived in the same read as the frame.
    if (answerReplaced) return 0;
    let limit = buffer.length;
    for (const start of FRAME_STARTS) {
      const index = buffer.indexOf(start);
      limit = Math.min(
        limit,
        index !== -1 ? index : buffer.length - partialMarkerLength(buffer, start)
      );
    }
    if (citationsSent) {
      limit = Math.min(limit, buffer.length - incompleteBracketLength(buffer));
    }
    return limit;
  };

  return {
    push(text: string) {
      buffer += text;
      drainFrames();
      const limit = emitLimit();
      if (limit > 0) {
        handlers.onChunk(buffer.slice(0, limit));
        buffer = buffer.slice(limit);
      }
    },

    close() {
      drainFrames();
      if (!answerReplaced && buffer.length > 0) {
        const hold = citationsSent ? incompleteBracketLength(buffer) : 0;
        if (hold < buffer.length) {
          handlers.onChunk(buffer.slice(0, buffer.length - hold));
        }
      }
      buffer = "";
      if (!citationsSent) {
        handlers.onCitations([]);
        citationsSent = true;
      }
    },
  };
}

export const chatApi = {
  /**
   * POST /chat/stream
   * The server sends `__CITATIONS__[...]__END_CITATIONS__` first, then answer tokens,
   * then optional `__ANSWER_FINAL__"..."__END_ANSWER_FINAL__` when the streamed text
   * was corrected, then optional `__CITATIONS_FINAL__[...]__END_CITATIONS__`.
   */
  async streamMessage(
    content: string,
    documentIds: string[],
    conversationId: string,
    onChunk: (chunk: string) => void,
    onCitations: (citations: Citation[]) => void,
    mode: ProductMode = "normal",
    signal?: AbortSignal,
    regenerate: boolean = false,
    onFinalAnswer?: (answer: string) => void
  ): Promise<void> {
    const response = await apiFetch("/chat/stream", {
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
      errorMessage:
        "The server could not generate an answer. Please try again",
    });

    const reader = response.body?.getReader();
    if (!reader) {
      throw new Error("Streaming is not supported by this browser.");
    }

    const decoder = new TextDecoder();
    const parser = createStreamParser({ onChunk, onCitations, onFinalAnswer });

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      parser.push(decoder.decode(value, { stream: true }));
    }

    parser.close();
  },
};
