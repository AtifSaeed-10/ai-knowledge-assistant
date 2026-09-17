import type { PDFDocumentProxy } from "pdfjs-dist";

import { sessionHeaders } from "@/lib/guestSession";

let workerReady = false;

export async function loadPdfjs() {
  const pdfjs = await import("pdfjs-dist");
  if (!workerReady) {
    pdfjs.GlobalWorkerOptions.workerSrc = "/pdf.worker.min.mjs";
    workerReady = true;
  }
  return pdfjs;
}

export async function loadPdfDocument(url: string): Promise<PDFDocumentProxy> {
  const pdfjs = await loadPdfjs();
  const task = pdfjs.getDocument({
    url,
    // The PDF route is owner-guarded, so the fetch needs the session identity.
    httpHeaders: sessionHeaders(),
    withCredentials: false,
    isEvalSupported: false,
  });
  return task.promise;
}

export function pdfFileUrlWithoutHash(url: string): string {
  const hash = url.indexOf("#");
  return hash === -1 ? url : url.slice(0, hash);
}
