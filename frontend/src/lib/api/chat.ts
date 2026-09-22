import type { Citation } from "@/types/citation";
import { ProductMode } from "@/types/mode";
import { apiFetch } from "./client";
import {
  displayNumberFromEvidenceId,
  incompleteBracketLength,
} from "@/lib/citations/markers";
import { displayNumberFromWebId, mergeAnswerCitations } from "@/lib/citations/web";
import type { EvidenceRegion } from "@/types/citation";

export interface ApiSource {
  document_id?: string;
  filename?: string;
  title?: string;
  url?: string;
  domain?: string;
  kind?: string;
  preview?: boolean | null;
  provider?: string | null;
  tier?: string | null;
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
const WEB_SOURCES_START = "__WEB_SOURCES__";
const WEB_SOURCES_END = "__END_WEB_SOURCES__";
const ANSWER_FINAL_START = "__ANSWER_FINAL__";
const ANSWER_FINAL_END = "__END_ANSWER_FINAL__";
const STATUS_START = "__STATUS__";
const STATUS_END = "__END_STATUS__";

const FRAME_STARTS = [
  CITATIONS_FINAL_START,
  CITATIONS_START,
  WEB_SOURCES_START,
  ANSWER_FINAL_START,
  STATUS_START,
];

export function mapSourceToCitation(src: ApiSource, idx: number): Citation {
  const rawPage = src.page ?? src.page_number;
  const pageNumber =
    typeof rawPage === "number" && Number.isFinite(rawPage) && rawPage >= 1
      ? Math.floor(rawPage)
      : null;
  const evidenceId = src.evidence_id || src.evidenceId || null;
  const displayNumber =
    displayNumberFromEvidenceId(evidenceId) ??
    displayNumberFromWebId(evidenceId);
  const quotes = Array.isArray(src.quotes)
    ? src.quotes.filter((item): item is string => typeof item === "string" && item.trim().length > 0)
    : [];
  const quote =
    typeof src.quote === "string" && src.quote.trim()
      ? src.quote.trim()
      : quotes[0] ?? null;
  const url = typeof src.url === "string" && src.url.trim() ? src.url.trim() : null;
  const isWeb =
    src.kind === "web" ||
    (src.content_type || "").toLowerCase() === "web" ||
    Boolean(url);
  const title =
    (typeof src.title === "string" && src.title.trim()) ||
    (typeof src.filename === "string" && src.filename.trim()) ||
    (typeof src.domain === "string" && src.domain.trim()) ||
    (isWeb ? "Web source" : "Unknown document");

  return {
    id: src.chunk_id || url || `cit-${Date.now()}-${idx}`,
    documentName: title,
    pageNumber,
    snippet: src.snippet ?? src.text,
    relevance: src.relevance ?? null,
    chunk_id: src.chunk_id ?? null,
    documentId: src.document_id || null,
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
    kind: isWeb ? "web" : "pdf",
    url,
    domain: typeof src.domain === "string" && src.domain.trim() ? src.domain.trim() : null,
    title: typeof src.title === "string" && src.title.trim() ? src.title.trim() : null,
    preview: src.preview === true,
    provider: typeof src.provider === "string" ? src.provider : null,
    tier: typeof src.tier === "string" && src.tier.trim() ? src.tier.trim() : null,
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

function tryParseStatus(payload: string): string {
  try {
    const raw = JSON.parse(payload) as { message?: unknown };
    return typeof raw.message === "string" ? raw.message : "";
  } catch {
    return "";
  }
}

type ControlEvent =
  | { kind: "citations"; citations: Citation[]; final: boolean }
  | { kind: "web_sources"; citations: Citation[] }
  | { kind: "answer"; answer: string }
  | { kind: "status"; message: string };

type FrameDef = {
  start: string;
  end: string;
  kind: ControlEvent["kind"] | "citations_final";
};

const FRAME_DEFS: FrameDef[] = [
  { start: STATUS_START, end: STATUS_END, kind: "status" },
  { start: ANSWER_FINAL_START, end: ANSWER_FINAL_END, kind: "answer" },
  { start: WEB_SOURCES_START, end: WEB_SOURCES_END, kind: "web_sources" },
  { start: CITATIONS_FINAL_START, end: CITATIONS_END, kind: "citations_final" },
  { start: CITATIONS_START, end: CITATIONS_END, kind: "citations" },
];

/** Remove the first complete control frame from the buffer, if there is one. */
function takeControlFrame(buffer: string): {
  buffer: string;
  event: ControlEvent | null;
  consumed: boolean;
} {
  let winner: { def: FrameDef; begin: number } | null = null;
  for (const def of FRAME_DEFS) {
    const begin = buffer.indexOf(def.start);
    if (begin === -1) continue;
    if (
      !winner ||
      begin < winner.begin ||
      (begin === winner.begin && def.start.length > winner.def.start.length)
    ) {
      winner = { def, begin };
    }
  }
  if (!winner) {
    return { buffer, event: null, consumed: false };
  }

  const { def, begin } = winner;
  const from = begin + def.start.length;
  const end = buffer.indexOf(def.end, from);
  if (end === -1) {
    return { buffer, event: null, consumed: false };
  }

  const payload = buffer.slice(from, end);
  const next = buffer.slice(0, begin) + buffer.slice(end + def.end.length);

  if (def.kind === "status") {
    return {
      buffer: next,
      event: { kind: "status", message: tryParseStatus(payload) },
      consumed: true,
    };
  }
  if (def.kind === "answer") {
    const answer = tryParseAnswer(payload);
    return {
      buffer: next,
      event: answer === null ? null : { kind: "answer", answer },
      consumed: true,
    };
  }
  if (def.kind === "web_sources") {
    return {
      buffer: next,
      event: { kind: "web_sources", citations: tryParseCitations(payload) },
      consumed: true,
    };
  }
  return {
    buffer: next,
    event: {
      kind: "citations",
      citations: tryParseCitations(payload),
      final: def.kind === "citations_final",
    },
    consumed: true,
  };
}

export interface StreamHandlers {
  onChunk: (chunk: string) => void;
  onCitations: (citations: Citation[]) => void;
  /** Server-validated answer that supersedes every token streamed so far. */
  onFinalAnswer?: (answer: string) => void;
  onStatus?: (message: string) => void;
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
  let lastCitations: Citation[] = [];

  const drainFrames = () => {
    while (true) {
      const parsed = takeControlFrame(buffer);
      buffer = parsed.buffer;
      if (!parsed.consumed) break;
      if (!parsed.event) continue;
      if (parsed.event.kind === "status") {
        handlers.onStatus?.(parsed.event.message);
        continue;
      }
      if (parsed.event.kind === "answer") {
        answerReplaced = true;
        handlers.onFinalAnswer?.(parsed.event.answer);
        continue;
      }
      if (parsed.event.kind === "web_sources") {
        lastCitations = mergeAnswerCitations(lastCitations, parsed.event.citations);
        handlers.onCitations(lastCitations);
        citationsSent = true;
        continue;
      }
      if (parsed.event.final || !citationsSent) {
        lastCitations = parsed.event.citations;
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
    onFinalAnswer?: (answer: string) => void,
    webFallbackEnabled: boolean = false,
    onStatus?: (message: string) => void
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
        web_fallback_enabled: webFallbackEnabled,
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
    const parser = createStreamParser({
      onChunk,
      onCitations,
      onFinalAnswer,
      onStatus,
    });

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      parser.push(decoder.decode(value, { stream: true }));
    }

    parser.close();
  },
};
