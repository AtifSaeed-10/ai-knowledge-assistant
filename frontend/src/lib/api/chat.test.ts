import { describe, expect, it } from "vitest";
import { incompleteBracketLength } from "@/lib/citations/markers";
import { mapSourceToCitation } from "./chat";

const CITATIONS_START = "__CITATIONS__";
const CITATIONS_FINAL_START = "__CITATIONS_FINAL__";
const CITATIONS_END = "__END_CITATIONS__";

function partialMarkerLength(value: string, marker: string): number {
  const max = Math.min(value.length, marker.length - 1);
  for (let size = max; size > 0; size -= 1) {
    if (value.endsWith(marker.slice(0, size))) return size;
  }
  return 0;
}

function tryParseCitations(payload: string): ReturnType<typeof mapSourceToCitation>[] {
  try {
    const raw = JSON.parse(payload) as Parameters<typeof mapSourceToCitation>[0][];
    return raw.map(mapSourceToCitation);
  } catch {
    return [];
  }
}

function stripControlMarkers(buffer: string): {
  buffer: string;
  citations: ReturnType<typeof mapSourceToCitation>[] | null;
} {
  for (const start of [CITATIONS_FINAL_START, CITATIONS_START]) {
    const begin = buffer.indexOf(start);
    const end = buffer.indexOf(CITATIONS_END);
    if (begin !== -1 && end !== -1 && end > begin) {
      const payload = buffer.slice(begin + start.length, end);
      const citations = tryParseCitations(payload);
      const next = buffer.slice(0, begin) + buffer.slice(end + CITATIONS_END.length);
      return { buffer: next, citations };
    }
  }
  return { buffer, citations: null };
}

function parseStream(chunks: string[]): {
  citations: ReturnType<typeof mapSourceToCitation>[];
  answer: string;
} {
  let buffer = "";
  let citationsSent = false;
  let answer = "";
  let citations: ReturnType<typeof mapSourceToCitation>[] = [];

  const consume = (done = false) => {
    while (true) {
      const parsed = stripControlMarkers(buffer);
      buffer = parsed.buffer;
      if (!parsed.citations) break;
      citations = parsed.citations;
      citationsSent = true;
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
      answer += buffer.slice(0, emitUpTo);
      buffer = buffer.slice(emitUpTo);
    }

    if (done && buffer.length > 0) {
      const hold = citationsSent ? incompleteBracketLength(buffer) : 0;
      if (hold < buffer.length) {
        answer += buffer.slice(0, buffer.length - hold);
      }
    }
  };

  for (const chunk of chunks) {
    buffer += chunk;
    consume();
  }
  consume(true);
  return { citations, answer };
}

describe("citation JSON through the stream", () => {
  it("keeps citation JSON and quoted markers intact", () => {
    const sources = [
      {
        document_id: "doc-a",
        filename: "ml.pdf",
        page: 17,
        chunk_id: "doc-a_38",
        relevance: 100,
        evidence_id: "E1",
        snippet: "A training set of examples with the correct responses.",
        quote: null,
      },
      {
        document_id: "doc-a",
        filename: "ml.pdf",
        page: 19,
        chunk_id: "doc-a_42",
        relevance: 100,
        evidence_id: "E2",
        snippet: "Consider teaching a dog a new trick.",
        quote: null,
      },
    ];
    const { citations, answer } = parseStream([
      `${CITATIONS_START}${JSON.stringify(sources)}${CITATIONS_END}`,
      "Supervised learning uses labeled examples.",
      '[E1:"A training set of examples with the correct responses."]',
      " Extra retrieved material is not cited.",
    ]);

    expect(citations).toHaveLength(2);
    expect(citations[0].evidenceId).toBe("E1");
    expect(citations[0].snippet).toBe("A training set of examples with the correct responses.");
    expect(citations[0].quote).toBeNull();
    expect(citations[1].evidenceId).toBe("E2");
    expect(citations[1].relevance).toBe(100);
    expect(answer).toContain('[E1:"A training set of examples with the correct responses."]');
    expect(answer).not.toContain("[E2]");
  });

  it("applies final validated citations after the answer", () => {
    const initial = [
      {
        document_id: "doc-a",
        filename: "ml.pdf",
        page: 17,
        chunk_id: "doc-a_38",
        relevance: 100,
        evidence_id: "E1",
        snippet: "A training set of examples.",
        quote: null,
      },
    ];
    const final = [
      {
        ...initial[0],
        quote: "A training set of examples.",
        quote_mapping_status: "exact",
        quote_highlight_available: true,
        quote_regions: [
          { page: 17, x0: 1, y0: 2, x1: 3, y1: 4, coord_space: "pdf" },
        ],
      },
    ];
    const { citations, answer } = parseStream([
      `${CITATIONS_START}${JSON.stringify(initial)}${CITATIONS_END}`,
      'Answer text.[E1:"A training set of examples."]',
      `__CITATIONS_FINAL__${JSON.stringify(final)}__END_CITATIONS__`,
    ]);

    expect(answer).toBe('Answer text.[E1:"A training set of examples."]');
    expect(citations).toHaveLength(1);
    expect(citations[0].quote).toBe("A training set of examples.");
    expect(citations[0].quoteHighlightAvailable).toBe(true);
    expect(citations[0].quoteRegions).toHaveLength(1);
  });
});
