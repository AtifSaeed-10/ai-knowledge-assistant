"use client";

import React from "react";
import { ChatContainer } from "@/components/chat/ChatContainer";
import { PdfDock } from "@/components/chat/PdfDock";

/** Chat on the left, optional document preview on the right. */
export function WorkspaceStage() {
  return (
    <div className="flex min-h-0 flex-1 gap-3">
      <div className="flex min-h-0 min-w-0 flex-1 flex-col">
        <ChatContainer />
      </div>
      <PdfDock />
    </div>
  );
}
