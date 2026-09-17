import { describe, expect, it } from "vitest";

import { citedDocumentIds, suggestFollowUps } from "./followUpSuggestions";

const MIXED_ANSWER = `Adolf Hitler
Adolf Hitler was a political figure who rapidly acquired and abused unprecedented personal power, dismantling established constitutional frameworks to construct personalized power structures indissolubly linked to himself 16. Rather than functioning as a distant ruler, he was directly involved across diverse political domains 17. By late 1922, party announcements increasingly designated him as the recognized leader of the NSDAP 7.

Supervised Learning
Supervised learning is a machine learning paradigm aimed at discovering a function that maps input vectors to correct target outputs based on paired training examples 1. Unlike unsupervised methods, supervised learning requires labeled datasets and is primarily used to solve classification and regression tasks.`;

describe("suggestFollowUps", () => {
  it("builds topic-specific chips from a mixed Hitler and ML answer", () => {
    const chips = suggestFollowUps(
      "who was hitler and what is supervised learning?",
      MIXED_ANSWER
    );

    expect(chips.length).toBeGreaterThanOrEqual(2);
    expect(chips.some((item) => /classification/i.test(item) && /regression/i.test(item))).toBe(
      true
    );
    expect(chips.some((item) => /NSDAP/i.test(item) || /Hitler/i.test(item))).toBe(true);
    expect(chips).not.toContain("What happens after that?");
    expect(chips).not.toContain("Explain that in simpler words");
    expect(chips).not.toContain("What are the key points?");
  });

  it("does not repeat the original question", () => {
    const chips = suggestFollowUps(
      "How does supervised learning work?",
      "Supervised Learning\nSupervised learning is a machine learning paradigm."
    );
    expect(chips.every((item) => !/how does supervised learning work/i.test(item))).toBe(
      true
    );
  });

  it("collects unique cited document ids", () => {
    expect(
      citedDocumentIds([
        { documentId: "hitler" },
        { documentId: "ml" },
        { documentId: "hitler" },
        { documentId: null },
      ])
    ).toEqual(["hitler", "ml"]);
  });
});
