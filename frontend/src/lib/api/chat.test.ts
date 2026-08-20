import { describe, expect, it } from "vitest";
import { incompleteBracketLength } from "@/lib/citations/markers";
import { mapSourceToCitation } from "./chat";

const CITATIONS_START = "__CITATIONS__";
const CITATIONS_END = "__END_CITATIONS__";

function parseStream(chunks: string[]): { citations: ReturnType<typeof mapSourceToCitation>[]; answer: string } {
  let buffer = "";
  let citationsSent = false;
  let answer = "";
  const citations: ReturnType<typeof mapSourceToCitation>[] = [];

  const consume = (done = false) => {
    if (!citationsSent) {
      const start = buffer.indexOf(CITATIONS_START);
      const end = buffer.indexOf(CITATIONS_END);
      if (start !== -1 && end !== -1 && end > start) {
        const payload = JSON.parse(buffer.slice(start + CITATIONS_START.length, end));
        payload.forEach((src: Parameters<typeof mapSourceToCitation>[0], idx: number) => {
          citations.push(mapSourceToCitation(src, idx));
        });
        citationsSent = true;
        buffer = buffer.slice(0, start) + buffer.slice(end + CITATIONS_END.length);
      }
    }
    let emitUpTo = buffer.length;
    if (!citationsSent) {
      const start = buffer.indexOf(CITATIONS_START);
      emitUpTo = start !== -1 ? start : buffer.length;
    } else if (!done) {
      emitUpTo = buffer.length - incompleteBracketLength(buffer);
    }
    if (emitUpTo > 0) {
      answer += buffer.slice(0, emitUpTo);
      buffer = buffer.slice(emitUpTo);
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
});
