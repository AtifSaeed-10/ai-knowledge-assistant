import { documentsApi } from "@/lib/api/documents";
import { findHeadingPage } from "@/lib/pdf/findHeadingPage";
import { pdfFileUrlWithoutHash } from "@/lib/pdf/pdfjs";
import type { Document } from "@/types/document";
import type { ChatCommand, SocialReply } from "./chatCommand";
import { resolvePreviewDocument } from "./pdfPanel";

export function socialReplyText(reply: SocialReply, readyDocumentCount: number): string {
  if (reply === "thanks") {
    return "Happy to help. Ask me anything else from your PDFs.";
  }
  if (reply === "farewell") {
    return "Bye — your chats and documents will be here when you come back.";
  }
  return readyDocumentCount > 0
    ? "Hello. Ask me anything about your PDFs and I will answer with the page it came from."
    : "Hello. Upload a PDF and I will answer questions about it with the exact page as proof.";
}

export function clampRequestedPage(page: number, pageCount: number | null): number {
  if (!Number.isFinite(page) || page < 1) return 1;
  const target = Math.floor(page);
  if (!pageCount || pageCount < 1) return target;
  return Math.min(target, pageCount);
}

function fileName(doc: Document | null): string {
  return doc?.name?.trim() || "the PDF";
}

export async function runWorkspaceCommand(
  command: Exclude<ChatCommand, { kind: "question" }>,
  options: {
    documents: Document[];
    selectedDocumentId: string | null;
    previewDocumentId: string | null;
    citationDocumentId?: string | null;
    visiblePage: number;
    pageCount: number | null;
    openPanel: (options?: { pinned?: boolean; documentId?: string }) => void;
    closePanel: () => void;
    requestPage: (page: number) => void;
  }
): Promise<string> {
  if (command.kind === "social") {
    const ready = options.documents.filter((doc) => doc.status === "ready").length;
    return socialReplyText(command.reply, ready);
  }

  if (command.kind === "close_panel") {
    options.closePanel();
    return "Closed the PDF so the chat has more room. Say “show the PDF” or click a citation to open it again.";
  }

  const doc = resolvePreviewDocument({
    documents: options.documents,
    selectedDocumentId: options.selectedDocumentId,
    citationDocumentId: options.citationDocumentId,
    previewDocumentId: options.previewDocumentId,
  });

  if (!doc) {
    return "Add a PDF first, then I can open a page or heading in it.";
  }

  const knownCount = doc.totalPages && doc.totalPages >= 1 ? doc.totalPages : options.pageCount;
  const title = fileName(doc);

  if (command.kind === "open_panel") {
    options.openPanel({ pinned: true, documentId: doc.id });
    return `Opened ${title}.`;
  }

  const goTo = (page: number, note?: string) => {
    options.openPanel({ pinned: true, documentId: doc.id });
    options.requestPage(page);
    return note ?? `Opened page ${page} of ${title}.`;
  };

  if (command.kind === "goto_first") {
    return goTo(1);
  }

  if (command.kind === "goto_last") {
    const last = knownCount && knownCount >= 1 ? knownCount : options.visiblePage;
    if (!knownCount) {
      options.openPanel({ pinned: true, documentId: doc.id });
      return `Opened ${title}. I do not yet know the last page number — use the preview to scroll to the end.`;
    }
    return goTo(last, `Opened the last page (${last}) of ${title}.`);
  }

  if (command.kind === "goto_next") {
    const current = Math.max(1, options.visiblePage || 1);
    const next = clampRequestedPage(current + 1, knownCount);
    if (knownCount && current >= knownCount) {
      return goTo(knownCount, `${title} already ends on page ${knownCount}.`);
    }
    return goTo(next);
  }

  if (command.kind === "goto_prev") {
    const current = Math.max(1, options.visiblePage || 1);
    if (current <= 1) {
      return goTo(1, `${title} is already on the first page.`);
    }
    return goTo(current - 1);
  }

  if (command.kind === "goto_page") {
    if (command.page < 1) {
      return goTo(1, `${title} starts at page 1, so I opened the first page.`);
    }
    const page = clampRequestedPage(command.page, knownCount);
    if (knownCount && command.page > knownCount) {
      return goTo(
        page,
        `${title} has ${knownCount} pages, so I opened the last page instead of page ${command.page}.`
      );
    }
    return goTo(page);
  }

  if (command.kind !== "goto_heading") {
    return "I can open a page, a heading, or the PDF preview.";
  }

  const url = pdfFileUrlWithoutHash(documentsApi.fileUrl(doc.id));
  options.openPanel({ pinned: true, documentId: doc.id });
  try {
    const found = await findHeadingPage(url, command.query);
    if (found.page) {
      options.requestPage(found.page);
      return `Opened “${command.query}” on page ${found.page} of ${title}.`;
    }
    return `I could not find a heading that says “${command.query}” in ${title}. Ask what it covers if you want me to search the text.`;
  } catch {
    return `I could not scan ${title} for “${command.query}”. Try opening a page number, or ask a question about that heading.`;
  }
}
