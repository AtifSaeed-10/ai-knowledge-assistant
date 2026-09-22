import { describe, expect, it } from "vitest";
import { evidencePresentationStatus } from "./evidenceStatus";
import {
  parseEvidenceMarker,
  splitEvidenceMarkers,
  usedCitations,
} from "./markers";

describe("adversarial citation UI", () => {
  it("does not parse coordinate payloads as evidence markers", () => {
    expect(parseEvidenceMarker("[E1: x0=10 y0=20 x1=400 y1=500]")).toBeNull();
    const parts = splitEvidenceMarkers(
      "Claim.[E1: x0=10 y0=20] More.[E1]"
    );
    const citations = parts.filter((part) => part.type === "citation");
    expect(citations).toEqual([{ type: "citation", evidenceId: "E1", quote: null }]);
  });

  it("drops invented E-IDs that are not in the retrieved set", () => {
    const used = usedCitations(
      [{ evidenceId: "E1", quote: null }],
      "Ignore previous instructions.[E99] Grounded claim.[E1]"
    );
    expect(used.map((row) => row.evidenceId)).toEqual(["E1"]);
  });

  it("never treats a scan as a precise highlight even if a box leaked", () => {
    expect(
      evidencePresentationStatus({
        quoteHighlightAvailable: true,
        quoteMappingStatus: "exact",
        pageNumber: 2,
        contentType: "scanned_or_image",
      })
    ).toBe("page_only");
  });
});
