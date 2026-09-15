import { describe, expect, it } from "vitest";

import {
  isConversationalFollowUp,
  isDeicticDocumentQuestion,
  isGenericWholeDocumentQuestion,
  isMultiDocumentQuestion,
  lastCitedDocumentId,
  matchDocumentByName,
  resolveDocumentScope,
  shouldRememberScopePin,
} from "./documentScope";

const outline = { id: "outline", name: "CS101_Course_Outline.pdf", status: "ready" };
const hitler = { id: "hitler", name: "Hitler_Biography.pdf", status: "ready" };
const docs = [outline, hitler];

function decide(
  question: string,
  extra: Partial<Parameters<typeof resolveDocumentScope>[0]> = {}
) {
  return resolveDocumentScope({
    question,
    mode: "normal",
    documents: docs,
    ...extra,
  });
}

describe("resolveDocumentScope", () => {
  it("uses the only ready PDF", () => {
    expect(
      resolveDocumentScope({
        question: "summarize this",
        mode: "normal",
        documents: [outline],
      })
    ).toEqual({ kind: "ready", documentIds: ["outline"], reason: "single" });
  });

  it("uses the focused selection and does not ask", () => {
    expect(
      decide("give me summary of this outline", {
        mode: "super_focused",
        selectedDocumentId: "outline",
      })
    ).toEqual({ kind: "ready", documentIds: ["outline"], reason: "focused" });
  });

  it("picks the file named in the question instead of the other PDF", () => {
    expect(decide("give me summary of this outline")).toEqual({
      kind: "ready",
      documentIds: ["outline"],
      reason: "filename",
    });
    expect(matchDocumentByName("this outline", docs)?.id).toBe("outline");
  });

  it("asks when this/summary is ambiguous and nothing is selected", () => {
    const decision = decide("summarize this", {
      selectedDocumentId: null,
      previewDocumentId: null,
      pinnedDocumentId: null,
      lastCitedDocumentId: null,
    });
    expect(decision.kind).toBe("clarify");
    if (decision.kind === "clarify") {
      expect(decision.candidates.map((item) => item.id)).toEqual(["outline", "hitler"]);
    }
  });

  it("uses the selected PDF for a pointing question", () => {
    expect(
      decide("summarize this", { selectedDocumentId: "outline" })
    ).toEqual({ kind: "ready", documentIds: ["outline"], reason: "selected" });
  });

  it("uses the open preview for this/the document", () => {
    expect(
      decide("summarize this", { previewDocumentId: "outline" })
    ).toEqual({ kind: "ready", documentIds: ["outline"], reason: "preview" });
  });

  it("stays on the conversation pin for follow-ups", () => {
    expect(decide("what is week 4", { pinnedDocumentId: "outline" })).toEqual({
      kind: "ready",
      documentIds: ["outline"],
      reason: "pinned",
    });
  });

  it("searches every PDF for compare/all and for a specific topic", () => {
    const everyPdf = { kind: "ready", documentIds: ["outline", "hitler"] };

    expect(decide("compare both documents")).toMatchObject(everyPdf);
    expect(decide("who was Hindenburg")).toMatchObject(everyPdf);
    expect(decide("what is the outline of chapter 3")).toMatchObject(everyPdf);
  });

  it("does not treat outline-of as pointing at a file", () => {
    expect(isDeicticDocumentQuestion("what is the outline of chapter 3")).toBe(false);
    expect(isDeicticDocumentQuestion("give me summary of this outline")).toBe(true);
    expect(isDeicticDocumentQuestion("what is week 4")).toBe(false);
    expect(isGenericWholeDocumentQuestion("give me a summary")).toBe(true);
    expect(isGenericWholeDocumentQuestion("what is week 4")).toBe(false);
    expect(isMultiDocumentQuestion("compare the two pdfs")).toBe(true);
    expect(
      isMultiDocumentQuestion(
        "search all documents: Hitler’s early life and supervised learning"
      )
    ).toBe(true);
    expect(
      isMultiDocumentQuestion("tell me about hitler early life and also supervised learning")
    ).toBe(true);
  });

  it("searches every PDF when one question names two topics", () => {
    expect(
      decide("search all documents: Hitler’s early life and supervised learning")
    ).toEqual({ kind: "ready", documentIds: ["outline", "hitler"], reason: "multi" });
    expect(
      decide("tell me about hitler early life and also tell me supervised learning")
    ).toEqual({ kind: "ready", documentIds: ["outline", "hitler"], reason: "multi" });
  });

  it("reads a single last-cited file and ignores mixed citations", () => {
    expect(
      lastCitedDocumentId([
        { citations: [{ documentId: "hitler" }, { documentId: "hitler" }] },
      ])
    ).toBe("hitler");
    expect(
      lastCitedDocumentId([
        { citations: [{ documentId: "hitler" }, { documentId: "outline" }] },
      ])
    ).toBeNull();
  });

  it("keeps a follow-up on the PDF the previous answer came from", () => {
    expect(
      decide("make it easier", { lastCitedDocumentId: "hitler" })
    ).toEqual({ kind: "ready", documentIds: ["hitler"], reason: "last-cited" });

    // The follow-up continues the last answer even when another file is pinned.
    expect(
      decide("explain it more simply", {
        lastCitedDocumentId: "hitler",
        pinnedDocumentId: "outline",
      })
    ).toEqual({ kind: "ready", documentIds: ["hitler"], reason: "last-cited" });
  });

  it("does not treat a fresh topic as a follow-up", () => {
    expect(isConversationalFollowUp("make it easier")).toBe(true);
    expect(isConversationalFollowUp("explain it more simply")).toBe(true);
    expect(isConversationalFollowUp("why?")).toBe(true);
    expect(isConversationalFollowUp("what is supervised learning")).toBe(false);
    expect(isConversationalFollowUp("who was Hindenburg")).toBe(false);

    expect(decide("who was Hindenburg", { lastCitedDocumentId: "hitler" })).toMatchObject({
      documentIds: ["outline", "hitler"],
    });
  });

  it("asks which PDF holds the author, but not who wrote a named work", () => {
    expect(isGenericWholeDocumentQuestion("who is the author")).toBe(true);
    expect(isGenericWholeDocumentQuestion("who wrote this")).toBe(true);
    expect(isGenericWholeDocumentQuestion("who is the author of Mein Kampf")).toBe(false);

    expect(
      decide("who is the author", {
        selectedDocumentId: null,
        previewDocumentId: null,
        pinnedDocumentId: null,
        lastCitedDocumentId: null,
      }).kind
    ).toBe("clarify");
  });

  it("remembers a one-file pin, but not an all-documents search", () => {
    expect(
      shouldRememberScopePin({ kind: "ready", documentIds: ["outline"], reason: "filename" })
    ).toBe(true);
    expect(
      shouldRememberScopePin({ kind: "ready", documentIds: ["outline", "hitler"], reason: "all" })
    ).toBe(false);
  });
});
