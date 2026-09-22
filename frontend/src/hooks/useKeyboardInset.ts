"use client";

import { useEffect } from "react";

/**
 * Publishes the height the on-screen keyboard is covering as
 * `--keyboard-inset`.
 *
 * Browsers that honour `interactive-widget=resizes-content` shrink the layout
 * viewport themselves, and there the measurement is simply zero.
 */
export function useKeyboardInset() {
  useEffect(() => {
    const viewport = window.visualViewport;
    const root = document.documentElement;
    if (!viewport) return;

    const update = () => {
      const covered = window.innerHeight - viewport.height - viewport.offsetTop;
      const inset = covered > 24 ? Math.round(covered) : 0;
      root.style.setProperty("--keyboard-inset", `${inset}px`);
    };

    update();
    viewport.addEventListener("resize", update);
    viewport.addEventListener("scroll", update);

    return () => {
      viewport.removeEventListener("resize", update);
      viewport.removeEventListener("scroll", update);
      root.style.removeProperty("--keyboard-inset");
    };
  }, []);
}
