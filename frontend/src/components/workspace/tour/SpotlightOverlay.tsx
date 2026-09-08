"use client";

import React, { useEffect, useLayoutEffect, useState } from "react";
import { createPortal } from "react-dom";
import { sameTourRect, type TourRect } from "@/lib/workspace/tourSteps";

function readRect(element: HTMLElement): TourRect | null {
  const rect = element.getBoundingClientRect();
  if (rect.width < 1 || rect.height < 1) return null;
  return {
    top: rect.top,
    left: rect.left,
    width: rect.width,
    height: rect.height,
  };
}

/**
 * Position of the `data-tour` element, followed frame by frame.
 *
 * The target moves for reasons that are hard to enumerate as events — the
 * mobile drawer sliding in, the sidebar resize handle, the PDF panel opening —
 * so we poll while the tour is on screen instead of stitching listeners
 * together. It runs for a few seconds at most and only compares four numbers.
 */
export function useTourAnchorRect(target: string | null): TourRect | null {
  const [rect, setRect] = useState<TourRect | null>(null);

  useEffect(() => {
    if (!target) {
      setRect(null);
      return;
    }

    let frame = 0;
    const tick = () => {
      const element = document.querySelector<HTMLElement>(
        `[data-tour="${target}"]`
      );
      const next = element ? readRect(element) : null;
      setRect((current) => (sameTourRect(current, next) ? current : next));
      frame = window.requestAnimationFrame(tick);
    };

    tick();
    return () => window.cancelAnimationFrame(frame);
  }, [target]);

  return rect;
}

export function useViewportSize(): { width: number; height: number } {
  const [size, setSize] = useState({ width: 0, height: 0 });

  useLayoutEffect(() => {
    const update = () =>
      setSize({ width: window.innerWidth, height: window.innerHeight });
    update();
    window.addEventListener("resize", update);
    return () => window.removeEventListener("resize", update);
  }, []);

  return size;
}

interface SpotlightOverlayProps {
  /** Cutout to keep bright. When null the whole screen is dimmed. */
  rect: TourRect | null;
  onDismiss: () => void;
  children: React.ReactNode;
}

/**
 * Full-screen scrim with a hole punched over the current step's target.
 *
 * The dim is a huge spread shadow on the cutout element, so the bright area
 * needs no compositing tricks. A separate transparent layer swallows clicks:
 * the tour advances from its own buttons, never from a stray click on the app.
 */
export function SpotlightOverlay({
  rect,
  onDismiss,
  children,
}: SpotlightOverlayProps) {
  const [mounted, setMounted] = useState(false);

  useEffect(() => setMounted(true), []);

  useEffect(() => {
    const returnFocusTo = document.activeElement as HTMLElement | null;
    const { overflow } = document.body.style;
    document.body.style.overflow = "hidden";

    return () => {
      document.body.style.overflow = overflow;
      returnFocusTo?.focus?.();
    };
  }, []);

  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key !== "Escape") return;
      event.stopPropagation();
      onDismiss();
    };

    document.addEventListener("keydown", handleKeyDown, true);
    return () => document.removeEventListener("keydown", handleKeyDown, true);
  }, [onDismiss]);

  if (!mounted) return null;

  return createPortal(
    <div className="fixed inset-0 z-[130]">
      <div className="absolute inset-0" aria-hidden />

      {rect ? (
        <div
          aria-hidden
          className="pointer-events-none absolute rounded-xl ring-2 ring-sage/70 transition-all duration-200 ease-out"
          style={{
            top: rect.top,
            left: rect.left,
            width: rect.width,
            height: rect.height,
            boxShadow: "0 0 0 9999px rgba(28, 36, 31, 0.55)",
          }}
        />
      ) : (
        <div className="pointer-events-none absolute inset-0 bg-ink/55" aria-hidden />
      )}

      {children}
    </div>,
    document.body
  );
}
