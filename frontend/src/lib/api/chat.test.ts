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
  statuses: string[];
} {
  let answer = "";
  let citations: Citation[] = [];
  const finalAnswers: string[] = [];
  const statuses: string[] = [];

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
    onStatus: (message) => {
      statuses.push(message);
    },
  });

  for (const chunk of chunks) parser.push(chunk);
  parser.close();

  return { citations, answer, finalAnswers, statuses };
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

  it("keeps web source frames out of the answer text", () => {
    const web = [
      {
        kind: "web",
        evidence_id: "W1",
        title: "Preview",
        url: "https://example.com/preview",
        domain: "example.com",
        snippet: "Development search result.",
        preview: true,
        content_type: "web",
      },
    ];
    const { citations, answer } = parseStream([
      `${CITATIONS_START}[]${CITATIONS_END}`,
      `__WEB_SOURCES__${JSON.stringify(web)}__END_WEB_SOURCES__`,
      "Your documents don't cover this question.",
    ]);

    expect(answer).toBe("Your documents don't cover this question.");
    expect(answer).not.toContain("__WEB_SOURCES__");
    expect(citations).toHaveLength(1);
    expect(citations[0].kind).toBe("web");
    expect(citations[0].url).toBe("https://example.com/preview");
  });

  it("surfaces search status without leaking markers into the answer", () => {
    const checking = JSON.stringify({
      step: "documents",
      message: "Checking your documents…",
    });
    const searching = JSON.stringify({
      step: "web",
      message: "Nothing in your documents. Searching the web…",
    });
    const { answer, statuses } = parseStream([
      `__STATUS__${checking}__END_STATUS__`,
      `__STATUS__${searching.slice(0, 12)}`,
      `${searching.slice(12)}__END_STATUS__`,
      `${CITATIONS_START}[]${CITATIONS_END}`,
      "Bitcoin is a decentralized cryptocurrency.",
    ]);

    expect(answer).toBe("Bitcoin is a decentralized cryptocurrency.");
    expect(answer).not.toContain("__STATUS__");
    expect(statuses[0]).toContain("Checking your documents");
    expect(statuses[1]).toContain("Searching the web");
  });

  it("keeps PDF cards when web sources arrive after a document answer", () => {
    const web = [
      {
        kind: "web",
        evidence_id: "W1",
        title: "IFAB",
        url: "https://www.theifab.com/news/2018-law-changes",
        domain: "theifab.com",
        snippet: "The 2018 revision clarified the moment of judgement.",
        preview: false,
        tier: "t1",
        content_type: "web",
      },
    ];
    const combined =
      "I couldn't find information in the provided document regarding the 2018 amendment. " +
      "The document covers the 1990s wording [E1].\n\n" +
      "The 2018 revision clarified that attacking players are judged at the moment the ball is played.";
    const mixed = [
      SOURCES[0],
      {
        kind: "web",
        evidence_id: "W1",
        title: "IFAB",
        url: "https://www.theifab.com/news/2018-law-changes",
        domain: "theifab.com",
        snippet: "The 2018 revision clarified the moment of judgement.",
        preview: false,
        tier: "t1",
        content_type: "web",
      },
    ];
    const { citations, answer } = parseStream([
      `${CITATIONS_START}${JSON.stringify(SOURCES)}${CITATIONS_END}`,
      "I couldn't find information in the provided document regarding the 2018 amendment. ",
      `__WEB_SOURCES__${JSON.stringify(web)}__END_WEB_SOURCES__`,
      `${ANSWER_FINAL_START}${JSON.stringify(combined)}${ANSWER_FINAL_END}`,
      `${CITATIONS_FINAL_START}${JSON.stringify(mixed)}${CITATIONS_END}`,
    ]);

    expect(answer).toBe(combined);
    expect(answer).toContain("1990s wording");
    expect(answer).toContain("2018 revision");
    expect(citations.some((item) => item.kind === "pdf")).toBe(true);
    expect(citations.some((item) => item.kind === "web")).toBe(true);
    expect(citations.find((item) => item.kind === "web")?.url).toContain("theifab.com");
  });
});

describe("source mapping", () => {
  it("keeps a missing page as null instead of guessing", () => {
    const citation = mapSourceToCitation({ chunk_id: "c1", filename: "a.pdf" }, 0);
    expect(citation.pageNumber).toBeNull();
    expect(citation.documentName).toBe("a.pdf");
  });

  it("maps a web source without inventing a PDF page", () => {
    const citation = mapSourceToCitation(
      {
        kind: "web",
        evidence_id: "W1",
        title: "Web lookup preview",
        url: "https://example.com/docusage-web-preview",
        domain: "example.com",
        snippet: "Development search result.",
        preview: true,
        provider: "mock",
        content_type: "web",
        chunk_id: "https://example.com/docusage-web-preview",
      },
      0
    );
    expect(citation.kind).toBe("web");
    expect(citation.displayNumber).toBe(1);
    expect(citation.pageNumber).toBeNull();
    expect(citation.url).toBe("https://example.com/docusage-web-preview");
    expect(citation.preview).toBe(true);
  });

  it("keeps authenticity tier on live web sources", () => {
    const citation = mapSourceToCitation(
      {
        kind: "web",
        evidence_id: "W1",
        title: "Laws of the Game",
        url: "https://www.theifab.com/laws",
        domain: "theifab.com",
        snippet: "A player is in an offside position if...",
        preview: false,
        provider: "tavily",
        tier: "t1",
        content_type: "web",
      },
      0
    );
    expect(citation.tier).toBe("t1");
    expect(citation.preview).toBe(false);
    expect(citation.kind).toBe("web");
  });
});
