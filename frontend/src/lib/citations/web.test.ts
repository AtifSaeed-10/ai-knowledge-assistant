import { describe, expect, it } from "vitest";
import {
  displayNumberFromWebId,
  hostnameFromUrl,
  isDocumentRefusal,
  isPreviewWebCitation,
  isWebCitation,
  listedAnswerSources,
  mergeAnswerCitations,
  stripWebMarkers,
  webSourceBadge,
} from "./web";
import type { Citation } from "@/types/citation";

describe("web citation helpers", () => {
  it("treats kind, content type, or a url as a web source", () => {
    expect(isWebCitation({ kind: "web" })).toBe(true);
    expect(isWebCitation({ contentType: "web" })).toBe(true);
    expect(isWebCitation({ url: "https://example.com/a" })).toBe(true);
    expect(isWebCitation({ kind: "pdf", documentName: "ml.pdf" })).toBe(false);
  });

    it("strips W-markers from visible web answers", () => {
      expect(
        stripWebMarkers(
          "GPT-6 Astra launched in 2026 [W2][W5]. It is OpenAI's latest model [W3]."
        )
      ).toBe("GPT-6 Astra launched in 2026. It is OpenAI's latest model.");
    });

  it("reads W-numbers without colliding with PDF E-numbers", () => {
    expect(displayNumberFromWebId("W2")).toBe(2);
    expect(displayNumberFromWebId("E2")).toBeNull();
  });

  it("lists web cards even when the answer has no [E#] markers", () => {
    const web: Citation = {
      id: "https://example.com/a",
      documentName: "Preview",
      pageNumber: null,
      kind: "web",
      url: "https://example.com/a",
      evidenceId: "W1",
      displayNumber: 1,
      preview: true,
    };
    const listed = listedAnswerSources([web], "Your documents don't cover this.");
    expect(listed).toHaveLength(1);
    expect(listed[0].kind).toBe("web");
  });

  it("recognises the stored document refusal copy", () => {
    expect(
      isDocumentRefusal("No relevant information found in the document.")
    ).toBe(true);
    expect(
      isDocumentRefusal(
        "I couldn't find information in the provided document regarding the 2018 amendment."
      )
    ).toBe(true);
    expect(isDocumentRefusal("Supervised learning uses labels.")).toBe(false);
  });

  it("merges web cards onto existing PDF citations", () => {
    const pdf: Citation = {
      id: "doc-a_0",
      documentName: "rules.pdf",
      pageNumber: 12,
      kind: "pdf",
      evidenceId: "E1",
      chunk_id: "doc-a_0",
    };
    const web: Citation = {
      id: "https://www.theifab.com/laws",
      documentName: "IFAB",
      pageNumber: null,
      kind: "web",
      url: "https://www.theifab.com/laws",
      evidenceId: "W1",
    };
    const merged = mergeAnswerCitations([pdf], [web]);
    expect(merged.map((item) => item.kind)).toEqual(["pdf", "web"]);
    expect(mergeAnswerCitations(merged, [web])).toHaveLength(2);
  });

  it("strips www from hostnames", () => {
    expect(hostnameFromUrl("https://www.theifab.com/laws")).toBe("theifab.com");
  });

  it("labels official and reference sources", () => {
    expect(
      webSourceBadge({
        domain: "theifab.com",
        tier: "t1",
        preview: false,
        provider: "tavily",
      })
    ).toBe("theifab.com · Official");
    expect(
      webSourceBadge({
        domain: "wikipedia.org",
        tier: "t2",
        preview: false,
        provider: "tavily",
      })
    ).toBe("wikipedia.org · Reference");
  });
});
