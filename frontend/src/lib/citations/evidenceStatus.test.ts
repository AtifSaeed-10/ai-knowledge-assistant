import { describe, expect, it } from "vitest";
import {
  contentTypeDetail,
  evidencePresentationStatus,
} from "./evidenceStatus";

describe("visual evidence presentation", () => {
  it("treats a figure with a page as page-only when there is no precise quote box", () => {
    expect(
      evidencePresentationStatus({
        quoteHighlightAvailable: false,
        quoteMappingStatus: "fallback_chunk",
        pageNumber: 6,
        contentType: "figure_caption",
      })
    ).toBe("page_only");
  });

  it("treats a table without a page as passage-only", () => {
    expect(
      evidencePresentationStatus({
        quoteHighlightAvailable: false,
        quoteMappingStatus: "none",
        pageNumber: null,
        contentType: "table",
      })
    ).toBe("passage_only");
  });

  it("keeps a tight caption highlight as precise", () => {
    expect(
      evidencePresentationStatus({
        quoteHighlightAvailable: true,
        quoteMappingStatus: "exact",
        pageNumber: 6,
        contentType: "figure_caption",
      })
    ).toBe("precise");
  });

  it("shows scan pages without claiming a highlight", () => {
    expect(
      evidencePresentationStatus({
        quoteHighlightAvailable: false,
        quoteMappingStatus: "no_layout",
        pageNumber: 2,
        contentType: "scanned_or_image",
      })
    ).toBe("page_only");
  });

  it("explains figure and table content types", () => {
    expect(contentTypeDetail("figure_caption")).toMatch(/figure/i);
    expect(contentTypeDetail("table")).toMatch(/table/i);
  });
});
