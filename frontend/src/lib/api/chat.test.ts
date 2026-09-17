import { describe, expect, it } from "vitest";
import type { Citation } from "@/types/citation";
import { createStreamParser, mapSourceToCitation } from "./chat";

const CITATIONS_START = "__CITATIONS__";
const CITATIONS_FINAL_START = "__CITATIONS_FINAL__";
const CITATIONS_END = "__END_CITATIONS__";
const ANSWER_FINAL_START = "__ANSWER_FINAL__";
const ANSWER_FINAL_END = "__END_ANSWER_FINAL__";

/** Feed raw server chunks through the real parser the app uses. */
function parseStream(chunks: string[]): {
  citations: Citation[];
  answer: string;
  finalAnswers: string[];
} {
  let answer = "";
  let citations: Citation[] = [];
  const finalAnswers: string[] = [];

  const parser = createStreamParser({
    onChunk: (chunk) => {
      answer += chunk;
    },
    onCitations: (next) => {
      citations = next;
    },
    onFinalAnswer: (next) => {
      finalAnswers.push(next);
      answer = next;
    },
  });

  for (const chunk of chunks) parser.push(chunk);
  parser.close();

  return { citations, answer, finalAnswers };
}

const SOURCES = [
  {
    document_id: "doc-a",
    filename: "ml.pdf",
    page: 17,
    chunk_id: "doc-a_38",
    relevance: 100,
    evidence_id: "E1",
    snippet: "A training set of examples with the correct responses.",
    quote: null,
    evidence_state: "citeable",
    citation_eligible: true,
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

describe("citation JSON through the stream", () => {
  it("keeps citation JSON and quoted markers intact", () => {
    const { citations, answer } = parseStream([
      `${CITATIONS_START}${JSON.stringify(SOURCES)}${CITATIONS_END}`,
      "Supervised learning uses labeled examples.",
      '[E1:"A training set of examples with the correct responses."]',
      " Extra retrieved material is not cited.",
    ]);

    expect(citations).toHaveLength(2);
    expect(citations[0].evidenceId).toBe("E1");
    expect(citations[0].evidenceState).toBe("citeable");
    expect(citations[0].citationEligible).toBe(true);
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
        quote_regions: [{ page: 17, x0: 1, y0: 2, x1: 3, y1: 4, coord_space: "pdf" }],
      },
    ];
    const { citations, answer } = parseStream([
      `${CITATIONS_START}${JSON.stringify(initial)}${CITATIONS_END}`,
      'Answer text.[E1:"A training set of examples."]',
      `${CITATIONS_FINAL_START}${JSON.stringify(final)}${CITATIONS_END}`,
    ]);

    expect(answer).toBe('Answer text.[E1:"A training set of examples."]');
    expect(citations).toHaveLength(1);
    expect(citations[0].quote).toBe("A training set of examples.");
    expect(citations[0].quoteHighlightAvailable).toBe(true);
    expect(citations[0].quoteRegions).toHaveLength(1);
  });
});

describe("repaired final answer replaces the streamed draft", () => {
  const REFUSAL = "I couldn't find that in the provided document.";
  const REPAIRED =
    "The provided passages discuss this. Supporting excerpt:\n\nEither party may terminate " +
    "the agreement by giving thirty days written notice. [E1]";

  it("replaces a streamed refusal with the repaired answer", () => {
    const { answer, finalAnswers } = parseStream([
      `${CITATIONS_START}${JSON.stringify(SOURCES)}${CITATIONS_END}`,
      REFUSAL,
      `${ANSWER_FINAL_START}${JSON.stringify(REPAIRED)}${ANSWER_FINAL_END}`,
      `${CITATIONS_FINAL_START}${JSON.stringify(SOURCES)}${CITATIONS_END}`,
    ]);

    expect(finalAnswers).toEqual([REPAIRED]);
    expect(answer).toBe(REPAIRED);
    expect(answer).not.toContain("couldn't find");
  });

  it("survives a frame split across reads and never shows marker text", () => {
    const frame = `${ANSWER_FINAL_START}${JSON.stringify(REPAIRED)}${ANSWER_FINAL_END}`;
    const cut = Math.floor(frame.length / 2);
    const { answer, finalAnswers } = parseStream([
      `${CITATIONS_START}${JSON.stringify(SOURCES)}${CITATIONS_END}`,
      "I couldn't find ",
      "that in the provided document.",
      frame.slice(0, cut),
      frame.slice(cut),
    ]);

    expect(finalAnswers).toEqual([REPAIRED]);
    expect(answer).toBe(REPAIRED);
    expect(answer).not.toContain("__ANSWER_FINAL__");
    expect(answer).not.toContain("__END_ANSWER_FINAL__");
  });

  it("drops draft tokens that share a read with the replacement frame", () => {
    const { answer } = parseStream([
      `${CITATIONS_START}${JSON.stringify(SOURCES)}${CITATIONS_END}`,
      `${REFUSAL}${ANSWER_FINAL_START}${JSON.stringify(REPAIRED)}${ANSWER_FINAL_END}`,
    ]);

    expect(answer).toBe(REPAIRED);
  });

  it("leaves the streamed answer alone when no replacement is sent", () => {
    const { answer, finalAnswers } = parseStream([
      `${CITATIONS_START}${JSON.stringify(SOURCES)}${CITATIONS_END}`,
      "Supervised learning uses labeled examples.",
      `${CITATIONS_FINAL_START}${JSON.stringify(SOURCES)}${CITATIONS_END}`,
    ]);

    expect(finalAnswers).toEqual([]);
    expect(answer).toBe("Supervised learning uses labeled examples.");
  });
});

describe("source mapping", () => {
  it("keeps a missing page as null instead of guessing", () => {
    const citation = mapSourceToCitation({ chunk_id: "c1", filename: "a.pdf" }, 0);
    expect(citation.pageNumber).toBeNull();
    expect(citation.documentName).toBe("a.pdf");
  });
});
