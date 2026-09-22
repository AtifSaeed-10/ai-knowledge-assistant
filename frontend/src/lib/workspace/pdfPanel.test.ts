import { describe, expect, it } from "vitest";

import {
  clampPdfPanelWidth,
  maxPdfWidthForWorkspace,
  PDF_PANEL_DEFAULT_WIDTH,
  PDF_PANEL_MIN_WIDTH,
  resolvePreviewDocument,
  shouldFollowAnswerCitation,
  shouldShowMobileOverlay,
} from "./pdfPanel";

describe("pdf panel width", () => {
  it("clamps to the allowed range", () => {
    expect(clampPdfPanelWidth(200)).toBe(PDF_PANEL_MIN_WIDTH);
    expect(clampPdfPanelWidth(900)).toBe(720);
    expect(clampPdfPanelWidth(Number.NaN)).toBe(PDF_PANEL_DEFAULT_WIDTH);
  });

  it("keeps a usable chat column on a narrow workspace", () => {
    expect(maxPdfWidthForWorkspace(900)).toBe(520);
    expect(maxPdfWidthForWorkspace(600)).toBe(PDF_PANEL_MIN_WIDTH);
  });
});

describe("which document the preview shows", () => {
  const docs = [{ id: "a" }, { id: "b" }, { id: "c" }];

  it("prefers the cited document", () => {
    expect(
      resolvePreviewDocument({
        documents: docs,
        selectedDocumentId: "a",
        citationDocumentId: "c",
      })?.id
    ).toBe("c");
  });

  it("prefers a just-uploaded preview over the selected document", () => {
    expect(
      resolvePreviewDocument({
        documents: docs,
        selectedDocumentId: "a",
        previewDocumentId: "b",
      })?.id
    ).toBe("b");
  });

  it("falls back to the selected document, then the first library item", () => {
    expect(
      resolvePreviewDocument({
        documents: docs,
        selectedDocumentId: "b",
      })?.id
    ).toBe("b");
    expect(
      resolvePreviewDocument({
        documents: docs,
        selectedDocumentId: null,
      })?.id
    ).toBe("a");
  });

  it("returns null when the library is empty", () => {
    expect(
      resolvePreviewDocument({
        documents: [],
        selectedDocumentId: "a",
        citationDocumentId: "a",
      })
    ).toBeNull();
  });
});

describe("when the preview should move", () => {
  it("follows a new answer only while the pane is already open", () => {
    expect(shouldFollowAnswerCitation({ isOpen: true, citationCount: 2 })).toBe(
      true
    );
    expect(shouldFollowAnswerCitation({ isOpen: false, citationCount: 2 })).toBe(
      false
    );
    expect(shouldFollowAnswerCitation({ isOpen: true, citationCount: 0 })).toBe(
      false
    );
  });

  it("keeps phones on chat after upload until the reader asks for the PDF", () => {
    expect(
      shouldShowMobileOverlay({
        isOpen: true,
        pinned: false,
        hasCitation: false,
      })
    ).toBe(false);
    expect(
      shouldShowMobileOverlay({
        isOpen: true,
        pinned: true,
        hasCitation: false,
      })
    ).toBe(true);
    expect(
      shouldShowMobileOverlay({
        isOpen: true,
        pinned: false,
        hasCitation: true,
      })
    ).toBe(true);
  });
});
