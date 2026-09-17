import { describe, expect, it } from "vitest";

import {
  shouldShowChatWorkspace,
  shouldSkipConversationReload,
} from "./workspaceView";

describe("shouldShowChatWorkspace", () => {
  it("shows the chat pane when documents exist", () => {
    expect(
      shouldShowChatWorkspace({
        documentCount: 1,
        conversationCount: 0,
        messageCount: 0,
        conversationId: "",
      })
    ).toBe(true);
  });

  it("keeps the chat pane after the last PDF is deleted if history remains", () => {
    expect(
      shouldShowChatWorkspace({
        documentCount: 0,
        conversationCount: 2,
        messageCount: 0,
        conversationId: "",
      })
    ).toBe(true);
  });

  it("shows the empty upload screen only with no files and no chats", () => {
    expect(
      shouldShowChatWorkspace({
        documentCount: 0,
        conversationCount: 0,
        messageCount: 0,
        conversationId: "",
      })
    ).toBe(false);
  });
});

describe("shouldSkipConversationReload", () => {
  it("refetches when the highlighted chat has no transcript yet", () => {
    expect(
      shouldSkipConversationReload({
        requestedId: "c1",
        currentId: "c1",
        conversationError: null,
        messageCount: 0,
        isSwitching: false,
      })
    ).toBe(false);
  });

  it("skips when the same chat is already showing messages", () => {
    expect(
      shouldSkipConversationReload({
        requestedId: "c1",
        currentId: "c1",
        conversationError: null,
        messageCount: 3,
        isSwitching: false,
      })
    ).toBe(true);
  });

  it("retries after a load error", () => {
    expect(
      shouldSkipConversationReload({
        requestedId: "c1",
        currentId: "c1",
        conversationError: "Could not open this conversation.",
        messageCount: 0,
        isSwitching: false,
      })
    ).toBe(false);
  });
});
