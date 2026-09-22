"use client";

import React, { useCallback, useEffect, useState } from "react";
import { SpotlightOverlay, useTourAnchorRect } from "./SpotlightOverlay";
import { TourPopover } from "./TourPopover";
import { EvidenceTourDemo } from "./EvidenceTourDemo";
import { WORKSPACE_TOUR_STEPS, inflateTourRect } from "@/lib/workspace/tourSteps";
import { hasSeenWorkspaceTour, rememberWorkspaceTourSeen } from "@/lib/site/firstRun";
import { useAuthStore } from "@/store/useAuthStore";
import { useDocumentStore } from "@/store/useDocumentStore";

interface WorkspaceTourProps {
  /** True while a step needs the document list on screen and expanded. */
  onNeedsSidebar: (needed: boolean) => void;
}

/**
 * A three-step spotlight tour, shown once, right after the workspace has its
 * first PDF. Everything it points at already exists — the tour only explains
 * the UI, it never changes retrieval or document scope.
 */
export function WorkspaceTour({ onNeedsSidebar }: WorkspaceTourProps) {
  const documents = useDocumentStore((state) => state.documents);
  const hasInitialized = useDocumentStore((state) => state.hasInitialized);
  const isSignupOpen = useAuthStore((state) => state.isSignupOpen);
  const accountSeenTour = useAuthStore((state) => state.user?.seenWorkspaceTour === true);

  const [stepIndex, setStepIndex] = useState<number | null>(null);
  const alreadySeen = hasSeenWorkspaceTour(accountSeenTour);

  useEffect(() => {
    if (alreadySeen) {
      setStepIndex(null);
      return;
    }
    if (!hasInitialized || documents.length === 0) return;
    if (isSignupOpen) return;
    setStepIndex((current) => (current === null ? 0 : current));
  }, [alreadySeen, documents.length, hasInitialized, isSignupOpen]);

  const step = stepIndex === null ? null : WORKSPACE_TOUR_STEPS[stepIndex];

  useEffect(() => {
    onNeedsSidebar(step?.needsSidebar === true);
  }, [onNeedsSidebar, step?.needsSidebar]);

  const finish = useCallback(() => {
    void rememberWorkspaceTourSeen();
    setStepIndex(null);
  }, []);

  const advance = useCallback(() => {
    if (stepIndex === null) return;
    if (stepIndex >= WORKSPACE_TOUR_STEPS.length - 1) {
      finish();
      return;
    }
    setStepIndex(stepIndex + 1);
  }, [finish, stepIndex]);

  const anchorRect = useTourAnchorRect(step?.target ?? null);

  // Signing up takes priority: never cover a modal the user has to answer.
  if (!step || stepIndex === null || isSignupOpen) return null;

  return (
    <SpotlightOverlay rect={inflateTourRect(anchorRect)} onDismiss={finish}>
      <TourPopover
        key={step.id}
        anchorRect={anchorRect}
        placement={step.placement}
        title={step.title}
        body={step.body}
        stepIndex={stepIndex}
        stepCount={WORKSPACE_TOUR_STEPS.length}
        onNext={advance}
        onSkip={finish}
      >
        {step.demo ? <EvidenceTourDemo /> : null}
      </TourPopover>
    </SpotlightOverlay>
  );
}
