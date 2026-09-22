"use client";

import React, { useEffect, useRef, useState } from "react";
import type { PDFDocumentProxy, PDFPageProxy, RenderTask } from "pdfjs-dist";
import {
  overlayRectsForPage,
  pagesForPdfViewer,
  type ChunkEvidence,
  type OverlayRect,
} from "@/lib/pdf/coords";
import { loadPdfDocument } from "@/lib/pdf/pdfjs";

type PageDim = {
  pageNumber: number;
  width: number;
  height: number;
};

function pageScale(containerWidth: number, pageWidth: number, zoom: number): number {
  if (containerWidth <= 0 || pageWidth <= 0 || zoom <= 0) return 0;
  return (containerWidth / pageWidth) * zoom;
}

function PdfPageCanvas({
  page,
  pageNumber,
  scale,
  evidence,
  focusHighlight,
}: {
  page: PDFPageProxy;
  pageNumber: number;
  scale: number;
  evidence: ChunkEvidence | null;
  focusHighlight: boolean;
}) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [cssSize, setCssSize] = useState({ width: 0, height: 0 });
  const [rects, setRects] = useState<OverlayRect[]>([]);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas || scale <= 0) return;

    const viewport = page.getViewport({ scale });
    const outputScale = window.devicePixelRatio || 1;
    canvas.width = Math.floor(viewport.width * outputScale);
    canvas.height = Math.floor(viewport.height * outputScale);

    const context = canvas.getContext("2d");
    if (!context) return;

    const renderTask: RenderTask = page.render({
      canvasContext: context,
      viewport,
      transform: outputScale !== 1 ? [outputScale, 0, 0, outputScale, 0, 0] : undefined,
    });

    const viewBox = [
      viewport.viewBox[0],
      viewport.viewBox[1],
      viewport.viewBox[2],
      viewport.viewBox[3],
    ] as [number, number, number, number];
    setCssSize({ width: viewport.width, height: viewport.height });
    setRects(overlayRectsForPage(evidence, pageNumber, viewBox, viewport));

    return () => {
      void renderTask.cancel();
    };
  }, [evidence, page, pageNumber, scale]);

  return (
    <div
      className="relative bg-white shadow-card"
      style={{ width: cssSize.width || undefined, height: cssSize.height || undefined }}
    >
      <canvas
        ref={canvasRef}
        className="relative z-0 block"
        style={{ width: cssSize.width, height: cssSize.height }}
      />
      {cssSize.width > 0 && (
        <div
          className="pointer-events-none absolute inset-0 z-10"
          data-evidence-overlay="true"
        >
          {rects.map((rect, index) => (
            <div
              key={`${rect.left}-${rect.top}-${rect.width}-${rect.height}-${index}`}
              data-evidence-highlight="true"
              data-evidence-focus={focusHighlight && index === 0 ? "true" : undefined}
              className="absolute rounded-[1px] mix-blend-multiply"
              style={{
                left: rect.left,
                top: rect.top,
                width: rect.width,
                height: rect.height,
                backgroundColor: "rgba(255, 213, 74, 0.28)",
              }}
            />
          ))}
        </div>
      )}
    </div>
  );
}

function PdfPageSlot({
  pdf,
  dim,
  containerWidth,
  zoom,
  evidence,
  focusPage,
  forceRender,
  scrollRoot,
}: {
  pdf: PDFDocumentProxy;
  dim: PageDim;
  containerWidth: number;
  zoom: number;
  evidence: ChunkEvidence | null;
  focusPage: number | null;
  forceRender: boolean;
  scrollRoot: HTMLElement | null;
}) {
  const slotRef = useRef<HTMLDivElement>(null);
  const [visible, setVisible] = useState(forceRender);
  const [page, setPage] = useState<PDFPageProxy | null>(null);
  const scale = pageScale(containerWidth, dim.width, zoom);
  const slotHeight = scale > 0 ? dim.height * scale : undefined;

  useEffect(() => {
    if (forceRender) setVisible(true);
  }, [forceRender]);

  useEffect(() => {
    const node = slotRef.current;
    if (!node) return;
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) setVisible(true);
      },
      { root: scrollRoot, rootMargin: "1600px 0px", threshold: 0 }
    );
    observer.observe(node);
    return () => observer.disconnect();
  }, [scrollRoot]);

  useEffect(() => {
    if (!visible) return;
    let cancelled = false;
    void pdf.getPage(dim.pageNumber).then((loaded) => {
      if (!cancelled) setPage(loaded);
    });
    return () => {
      cancelled = true;
    };
  }, [dim.pageNumber, pdf, visible]);

  return (
    <div
      ref={slotRef}
      data-pdf-page={dim.pageNumber}
      className="mx-auto mb-4"
      style={{ width: scale > 0 ? dim.width * scale : undefined, minHeight: slotHeight }}
    >
      {visible && page && scale > 0 ? (
        <PdfPageCanvas
          page={page}
          pageNumber={dim.pageNumber}
          scale={scale}
          evidence={evidence}
          focusHighlight={focusPage === dim.pageNumber}
        />
      ) : null}
    </div>
  );
}

export function PdfEvidenceViewer({
  fileUrl,
  focusPage,
  focusNonce,
  evidence,
  scale,
  onReady,
  onError,
  onPageCount,
  onVisiblePage,
}: {
  fileUrl: string;
  focusPage: number | null;
  focusNonce?: number;
  evidence: ChunkEvidence | null;
  scale: number;
  onReady: () => void;
  onError: () => void;
  onPageCount?: (count: number) => void;
  onVisiblePage?: (page: number) => void;
}) {
  const widthRef = useRef<HTMLDivElement>(null);
  const scrollRef = useRef<HTMLDivElement>(null);
  const onReadyRef = useRef(onReady);
  const onErrorRef = useRef(onError);
  const onPageCountRef = useRef(onPageCount);
  const onVisiblePageRef = useRef(onVisiblePage);
  const readyRef = useRef(false);

  const [containerWidth, setContainerWidth] = useState(0);
  const [scrollRoot, setScrollRoot] = useState<HTMLElement | null>(null);
  const [documentProxy, setDocumentProxy] = useState<PDFDocumentProxy | null>(null);
  const [dims, setDims] = useState<PageDim[]>([]);

  onReadyRef.current = onReady;
  onErrorRef.current = onError;
  onPageCountRef.current = onPageCount;
  onVisiblePageRef.current = onVisiblePage;

  useEffect(() => {
    setScrollRoot(scrollRef.current);
  }, []);

  useEffect(() => {
    const node = widthRef.current;
    if (!node) return;
    const observer = new ResizeObserver((entries) => {
      const width = Math.floor(entries[0]?.contentRect.width || 0);
      if (width > 0) setContainerWidth(width);
    });
    observer.observe(node);
    setContainerWidth(Math.floor(node.getBoundingClientRect().width));
    return () => observer.disconnect();
  }, []);

  useEffect(() => {
    let cancelled = false;
    readyRef.current = false;
    setDocumentProxy(null);
    setDims([]);

    void (async () => {
      try {
        const pdf = await loadPdfDocument(fileUrl);
        if (cancelled) {
          void pdf.destroy();
          return;
        }
        const nextDims: PageDim[] = [];
        for (const pageNumber of pagesForPdfViewer(pdf.numPages)) {
          const page = await pdf.getPage(pageNumber);
          if (cancelled) {
            void pdf.destroy();
            return;
          }
          const base = page.getViewport({ scale: 1 });
          nextDims.push({ pageNumber, width: base.width, height: base.height });
        }
        setDocumentProxy(pdf);
        setDims(nextDims);
        onPageCountRef.current?.(pdf.numPages);
      } catch {
        if (!cancelled) onErrorRef.current();
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [fileUrl]);

  useEffect(() => {
    return () => {
      void documentProxy?.destroy();
    };
  }, [documentProxy]);

  const canLayout = Boolean(documentProxy && dims.length > 0 && containerWidth > 0);

  useEffect(() => {
    if (!canLayout || readyRef.current) return;
    readyRef.current = true;
    onReadyRef.current();
  }, [canLayout]);

  useEffect(() => {
    if (!canLayout) return;
    const rawPage = focusPage && focusPage >= 1 ? focusPage : 1;
    const targetPage = dims.length > 0 ? Math.min(rawPage, dims.length) : rawPage;
    let cancelled = false;
    let tries = 0;
    let timer = 0;

    const tick = () => {
      if (cancelled) return;
      const pageNode = scrollRef.current?.querySelector<HTMLElement>(
        `[data-pdf-page="${targetPage}"]`
      );
      const highlight = pageNode?.querySelector<HTMLElement>("[data-evidence-focus='true']");
      (highlight || pageNode)?.scrollIntoView({ block: "center", inline: "nearest" });
      tries += 1;
      if (!highlight && tries < 12) {
        timer = window.setTimeout(tick, 50);
      }
    };

    const frame = window.requestAnimationFrame(tick);
    return () => {
      cancelled = true;
      window.cancelAnimationFrame(frame);
      window.clearTimeout(timer);
    };
  }, [canLayout, dims.length, evidence?.chunk_id, evidence?.highlight_available, evidence?.quote, evidence?.quote_highlight_available, focusNonce, focusPage]);

  useEffect(() => {
    const root = scrollRef.current;
    if (!root || !canLayout) return;

    let frame = 0;
    const reportVisiblePage = () => {
      const mid = root.getBoundingClientRect().top + root.clientHeight / 2;
      let bestPage = 1;
      let bestDistance = Number.POSITIVE_INFINITY;
      root.querySelectorAll<HTMLElement>("[data-pdf-page]").forEach((node) => {
        const page = Number(node.dataset.pdfPage);
        if (!Number.isFinite(page) || page < 1) return;
        const rect = node.getBoundingClientRect();
        const distance = Math.abs((rect.top + rect.bottom) / 2 - mid);
        if (distance < bestDistance) {
          bestDistance = distance;
          bestPage = page;
        }
      });
      onVisiblePageRef.current?.(bestPage);
    };

    const onScroll = () => {
      window.cancelAnimationFrame(frame);
      frame = window.requestAnimationFrame(reportVisiblePage);
    };

    reportVisiblePage();
    root.addEventListener("scroll", onScroll, { passive: true });
    return () => {
      window.cancelAnimationFrame(frame);
      root.removeEventListener("scroll", onScroll);
    };
  }, [canLayout, dims.length]);

  const forcePages = new Set(
    [focusPage, (focusPage || 1) - 1, (focusPage || 1) + 1].filter(
      (page): page is number => typeof page === "number" && page >= 1
    )
  );

  return (
    <div ref={scrollRef} data-pdf-scroll="true" className="h-full overflow-auto">
      <div ref={widthRef} className="px-4 py-4">
        {documentProxy &&
          dims.map((dim) => (
            <PdfPageSlot
              key={dim.pageNumber}
              pdf={documentProxy}
              dim={dim}
              containerWidth={containerWidth}
              zoom={scale}
              evidence={evidence}
              focusPage={focusPage}
              forceRender={forcePages.has(dim.pageNumber)}
              scrollRoot={scrollRoot}
            />
          ))}
      </div>
    </div>
  );
}
