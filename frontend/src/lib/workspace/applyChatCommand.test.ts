import { describe, expect, it, vi } from "vitest";

vi.mock("@/lib/pdf/findHeadingPage", () => ({
  findHeadingPage: vi.fn(),
}));

import { findHeadingPage } from "@/lib/pdf/findHeadingPage";
import { clampRequestedPage, runWorkspaceCommand } from "./applyChatCommand";

const doc = {
  id: "doc-1",
  name: "outline.pdf",
  size: 1,
  status: "ready" as const,
  uploadedAt: new Date(),
  totalPages: 40,
};

function deps() {
  return {
    documents: [doc],
    selectedDocumentId: null as string | null,
    previewDocumentId: null as string | null,
    visiblePage: 3,
    pageCount: 40,
    openPanel: vi.fn(),
    closePanel: vi.fn(),
    requestPage: vi.fn(),
  };
}

describe("runWorkspaceCommand", () => {
  it("opens a page without inventing content", async () => {
    const options = deps();
    const message = await runWorkspaceCommand({ kind: "goto_page", page: 50 }, options);
    expect(options.requestPage).toHaveBeenCalledWith(40);
    expect(message).toContain("40 pages");
    expect(message).not.toMatch(/Schelling/i);
  });

  it("asks for a PDF when the library is empty", async () => {
    const options = deps();
    options.documents = [];
    const message = await runWorkspaceCommand({ kind: "goto_page", page: 2 }, options);
    expect(options.requestPage).not.toHaveBeenCalled();
    expect(message).toContain("Add a PDF");
  });

  it("closes the pane on hide", async () => {
    const options = deps();
    const message = await runWorkspaceCommand({ kind: "close_panel" }, options);
    expect(options.closePanel).toHaveBeenCalled();
    expect(message.toLowerCase()).toContain("closed");
  });

  it("opens page 1 when asked for page 0", async () => {
    const options = deps();
    const message = await runWorkspaceCommand({ kind: "goto_page", page: 0 }, options);
    expect(options.requestPage).toHaveBeenCalledWith(1);
    expect(message).toContain("page 1");
  });

  it("stays on the last page when next would overflow", async () => {
    const options = deps();
    options.visiblePage = 40;
    const message = await runWorkspaceCommand({ kind: "goto_next" }, options);
    expect(options.requestPage).toHaveBeenCalledWith(40);
    expect(message).toContain("already ends");
  });

  it("stays on page 1 when previous would underflow", async () => {
    const options = deps();
    options.visiblePage = 1;
    const message = await runWorkspaceCommand({ kind: "goto_prev" }, options);
    expect(options.requestPage).toHaveBeenCalledWith(1);
    expect(message).toContain("first page");
  });

  it("does not jump when a heading is missing", async () => {
    const options = deps();
    vi.mocked(findHeadingPage).mockResolvedValue({ page: null, pageCount: 40 });
    const message = await runWorkspaceCommand(
      { kind: "goto_heading", query: "week 4" },
      options
    );
    expect(options.requestPage).not.toHaveBeenCalled();
    expect(message).toContain("could not find");
  });
});

describe("clampRequestedPage", () => {
  it("caps an out-of-range page", () => {
    expect(clampRequestedPage(50, 40)).toBe(40);
    expect(clampRequestedPage(0, 40)).toBe(1);
    expect(clampRequestedPage(12, null)).toBe(12);
  });
});
