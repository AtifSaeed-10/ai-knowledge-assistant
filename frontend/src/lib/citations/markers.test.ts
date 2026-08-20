import { describe, expect, it } from "vitest";
import {
  incompleteBracketLength,
  parseEvidenceMarker,
  splitEvidenceMarkers,
  toDisplayCitationText,
  usedCitations,
  withAnswerQuotes,
} from "./markers";

describe("quoted evidence markers", () => {
  it("parses a plain E-ID", () => {
    expect(parseEvidenceMarker("[E14]")).toEqual({
      evidenceId: "E14",
      quote: null,
    });
  });

  it("parses a verbatim quote without changing the E-ID", () => {
    expect(
      parseEvidenceMarker('[E14:"Supervised learning uses labeled examples."]')
    ).toEqual({
      evidenceId: "E14",
      quote: "Supervised learning uses labeled examples.",
    });
  });

  it("parses the pipe quote form", () => {
    expect(
      parseEvidenceMarker('[E14|quote="Supervised learning uses labeled examples."]')
    ).toEqual({
      evidenceId: "E14",
      quote: "Supervised learning uses labeled examples.",
    });
  });

  it("keeps two quotes from the same E-ID distinct", () => {
    const parts = splitEvidenceMarkers(
      'A.[E1:"supervised learning uses labeled examples"] B.[E1:"classification and regression"]'
    );
    const citations = parts.filter((part) => part.type === "citation");
    expect(citations).toEqual([
      {
        type: "citation",
        evidenceId: "E1",
        quote: "supervised learning uses labeled examples",
      },
      {
        type: "citation",
        evidenceId: "E1",
        quote: "classification and regression",
      },
    ]);
  });

  it("strips quotes from copied/exported display text", () => {
    expect(
      toDisplayCitationText(
        'A claim.[E14:"Supervised learning uses labeled examples."]'
      )
    ).toBe("A claim.[14]");
  });

  it("holds back an unclosed quoted marker", () => {
    expect(incompleteBracketLength('Hello [E1:"labeled examples')).toBe(
      '[E1:"labeled examples'.length
    );
    expect(incompleteBracketLength('Hello [E1:"labeled examples"]')).toBe(0);
  });

  it("keeps quoted markers intact across chunked streaming", () => {
    const chunks = ['Uses labels.', '[E1:"Labeled ', 'examples."] Also [E2] extra.'];
    let shown = "";
    let buffer = "";
    for (const chunk of chunks) {
      buffer += chunk;
      const hold = incompleteBracketLength(buffer);
      shown += buffer.slice(0, buffer.length - hold);
      buffer = hold > 0 ? buffer.slice(buffer.length - hold) : "";
    }
    shown += buffer;
    const citations = splitEvidenceMarkers(shown).filter((part) => part.type === "citation");
    expect(citations).toEqual([
      {
        type: "citation",
        evidenceId: "E1",
        quote: "Labeled examples.",
      },
      {
        type: "citation",
        evidenceId: "E2",
        quote: null,
      },
    ]);
  });
});

describe("answer quotes vs retrieved evidence", () => {
  it("attaches quotes only to E-IDs used in the answer", () => {
    const citations = [
      { evidenceId: "E1", quote: null },
      { evidenceId: "E2", quote: null },
      { evidenceId: "E3", quote: null },
    ];
    const content =
      'Supervised learning uses labeled examples.[E1:"supervised learning uses labeled examples"]';
    expect(withAnswerQuotes(citations, content)).toEqual([
      { evidenceId: "E1", quote: "supervised learning uses labeled examples" },
      { evidenceId: "E2", quote: null },
      { evidenceId: "E3", quote: null },
    ]);
  });

  it("keeps multiple cited quotes without inventing extra sources", () => {
    const citations = [
      { evidenceId: "E1", quote: null },
      { evidenceId: "E2", quote: null },
    ];
    const content =
      'A.[E1:"supervised learning uses labeled examples"] B.[E2:"classification and regression"]';
    expect(withAnswerQuotes(citations, content).map((item) => item.quote)).toEqual([
      "supervised learning uses labeled examples",
      "classification and regression",
    ]);
  });

  it("lists only inline-cited sources in first-appearance order", () => {
    const citations = [
      { evidenceId: "E1", id: "c1" },
      { evidenceId: "E2", id: "c2" },
      { evidenceId: "E3", id: "c3" },
      { evidenceId: "E5", id: "c5" },
    ];
    const content =
      'A definition.[E3:"unsupervised learning uses unlabeled data"] An example.[E1:"clustering groups similar items"]';
    expect(usedCitations(citations, content).map((item) => item.evidenceId)).toEqual([
      "E3",
      "E1",
    ]);
  });
});
