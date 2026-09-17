import { describe, expect, it } from "vitest";

import { isStoredFileName, resolveCitationDocumentName } from "./documentName";

const library = [{ id: "doc-1", name: "CS101_Course_Outline.pdf" }];

describe("resolveCitationDocumentName", () => {
  it("prefers the uploaded name over the on-disk name", () => {
    expect(
      resolveCitationDocumentName(
        {
          documentId: "doc-1",
          documentName: "5733c748-760a-4f6d-be25-83fae23369bb.pdf",
        },
        library
      )
    ).toBe("CS101_Course_Outline.pdf");
  });

  it("never shows a stored id when the library has not loaded", () => {
    expect(
      resolveCitationDocumentName(
        {
          documentId: "doc-9",
          documentName: "5733c748-760a-4f6d-be25-83fae23369bb.pdf",
        },
        []
      )
    ).toBe("Source");
  });

  it("keeps a real filename that the backend already resolved", () => {
    expect(
      resolveCitationDocumentName(
        { documentId: "doc-9", documentName: "Hitler_Biography.pdf" },
        []
      )
    ).toBe("Hitler_Biography.pdf");
  });

  it("recognises the stored PDF name pattern", () => {
    expect(isStoredFileName("5733c748-760a-4f6d-be25-83fae23369bb.pdf")).toBe(true);
    expect(isStoredFileName("Hitler_Biography.pdf")).toBe(false);
  });
});
