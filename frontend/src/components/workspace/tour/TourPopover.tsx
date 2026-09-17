"use client";

import React, {
  useCallback,
  useEffect,
  useId,
  useLayoutEffect,
  useRef,
  useState,
} from "react";
import { cn } from "@/lib/cn";
import {
  placeTourCard,
  type TourPlacement,
  type TourRect,
} from "@/lib/workspace/tourSteps";
import { useViewportSize } from "./SpotlightOverlay";

const FOCUSABLE =
  'a[href], button:not([disabled]), textarea:not([disabled]), input:not([disabled]), select:not([disabled]), [tabindex]:not([tabindex="-1"])';

const ARROW_EDGE = 20;

interface TourPopoverProps {
  anchorRect: TourRect | null;
  placement: TourPlacement;
  title: string;
  body: string;
  stepIndex: number;
  stepCount: number;
  onNext: () => void;
  onSkip: () => void;
  /** Optional illustration rendered above the copy. */
  children?: React.ReactNode;
}

export function TourPopover({
  anchorRect,
  placement,
  title,
  body,
  stepIndex,
  stepCount,
  onNext,
  onSkip,
  children,
}: TourPopoverProps) {
  const cardRef = useRef<HTMLDivElement>(null);
  const nextRef = useRef<HTMLButtonElement>(null);
  const [card, setCard] = useState({ width: 320, height: 200 });
  const viewport = useViewportSize();
  const titleId = useId();
  const bodyId = useId();

  useLayoutEffect(() => {
    const element = cardRef.current;
    if (!element) return;

    const measure = () => {
      const rect = element.getBoundingClientRect();
      setCard((current) =>
        Math.abs(current.width - rect.width) < 0.5 &&
        Math.abs(current.height - rect.height) < 0.5
          ? current
          : { width: rect.width, height: rect.height }
      );
    };

    measure();
    const observer = new ResizeObserver(measure);
    observer.observe(element);
    return () => observer.disconnect();
  }, []);

  useEffect(() => {
    const timer = window.setTimeout(() => nextRef.current?.focus(), 0);
    return () => window.clearTimeout(timer);
  }, []);

  const handleKeyDown = useCallback((event: React.KeyboardEvent) => {
    if (event.key !== "Tab" || !cardRef.current) return;

    const focusable = Array.from(
      cardRef.current.querySelectorAll<HTMLElement>(FOCUSABLE)
    ).filter((element) => element.offsetParent !== null);

    if (focusable.length === 0) {
      event.preventDefault();
      return;
    }

    const first = focusable[0];
    const last = focusable[focusable.length - 1];
    const active = document.activeElement;

    if (event.shiftKey && (active === first || active === cardRef.current)) {
      event.preventDefault();
      last.focus();
    } else if (!event.shiftKey && active === last) {
      event.preventDefault();
      first.focus();
    }
  }, []);

  const position = placeTourCard({
    anchor: anchorRect,
    viewport,
    card,
    placement,
  });

  const arrow = getArrowStyle(anchorRect, position, card);
  const isLastStep = stepIndex === stepCount - 1;

  return (
    <div
      ref={cardRef}
      role="dialog"
      aria-modal="true"
      aria-labelledby={titleId}
      aria-describedby={bodyId}
      tabIndex={-1}
      onKeyDown={handleKeyDown}
      className={cn(
        "pointer-events-auto absolute animate-rise-in rounded-2xl border border-line bg-surface p-5 shadow-overlay outline-none",
        children
          ? "w-[min(26rem,calc(100vw-2rem))]"
          : "w-[min(20rem,calc(100vw-2rem))]"
      )}
      style={{ top: position.top, left: position.left }}
    >
      {arrow ? (
        <span
          aria-hidden
          className="absolute h-3 w-3 rotate-45 border-b border-r border-line bg-surface"
          style={arrow}
        />
      ) : null}

      {children ? <div className="mb-4">{children}</div> : null}

      <p className="text-label font-semibold uppercase tracking-[0.08em] text-ink-subtle">
        Step {stepIndex + 1} of {stepCount}
      </p>
      <h2
        id={titleId}
        className="mt-1.5 text-title font-semibold tracking-[-0.01em] text-ink"
      >
        {title}
      </h2>
      <p id={bodyId} className="mt-1.5 text-ui leading-relaxed text-ink-muted">
        {body}
      </p>

      <div className="mt-4 flex items-center justify-between gap-3">
        {isLastStep ? (
          <span />
        ) : (
          <button
            type="button"
            onClick={onSkip}
            className="rounded-lg px-2 py-1.5 text-meta font-medium text-ink-muted transition-colors hover:bg-surface-muted hover:text-ink"
          >
            Skip tour
          </button>
        )}
        <button
          ref={nextRef}
          type="button"
          onClick={onNext}
          className="rounded-lg bg-olive px-3.5 py-1.5 text-ui font-semibold text-white transition-colors hover:bg-olive-dark focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-olive"
        >
          {isLastStep ? "Got it" : "Next"}
        </button>
      </div>
    </div>
  );
}

/**
 * Nudges a small rotated square onto the card edge that faces the target, so
 * it is obvious which part of the workspace the card is talking about.
 */
function getArrowStyle(
  anchor: TourRect | null,
  position: { top: number; left: number; placement: TourPlacement },
  card: { width: number; height: number }
): React.CSSProperties | null {
  if (!anchor || position.placement === "center") return null;

  const clampOffset = (value: number, extent: number) =>
    Math.min(Math.max(value, ARROW_EDGE), Math.max(ARROW_EDGE, extent - ARROW_EDGE));

  if (position.placement === "right" || position.placement === "left") {
    const top = clampOffset(
      anchor.top + anchor.height / 2 - position.top,
      card.height
    );
    return position.placement === "right"
      ? { top, left: -6, marginTop: -6, transform: "rotate(135deg)" }
      : { top, right: -6, marginTop: -6, transform: "rotate(-45deg)" };
  }

  const left = clampOffset(
    anchor.left + anchor.width / 2 - position.left,
    card.width
  );
  return position.placement === "bottom"
    ? { left, top: -6, marginLeft: -6, transform: "rotate(-135deg)" }
    : { left, bottom: -6, marginLeft: -6, transform: "rotate(45deg)" };
}
