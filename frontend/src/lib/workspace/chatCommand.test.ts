import { describe, expect, it } from "vitest";

import { classifyChatCommand, isSocialMessage, isWorkspaceCommand } from "./chatCommand";

describe("classifyChatCommand", () => {
  it("treats open-page phrasing as navigation, not a question", () => {
    expect(classifyChatCommand("open the page 50")).toEqual({
      kind: "goto_page",
      page: 50,
    });
    expect(classifyChatCommand("go to page 50")).toEqual({
      kind: "goto_page",
      page: 50,
    });
    expect(classifyChatCommand("show p. 12")).toEqual({
      kind: "goto_page",
      page: 12,
    });
    expect(classifyChatCommand("page 50")).toEqual({
      kind: "goto_page",
      page: 50,
    });
    expect(classifyChatCommand("open page fifty")).toEqual({
      kind: "goto_page",
      page: 50,
    });
    expect(classifyChatCommand("turn to page 50")).toEqual({
      kind: "goto_page",
      page: 50,
    });
    expect(classifyChatCommand("view page 50")).toEqual({
      kind: "goto_page",
      page: 50,
    });
    expect(classifyChatCommand("can you open page 50")).toEqual({
      kind: "goto_page",
      page: 50,
    });
    expect(classifyChatCommand("open page 50.")).toEqual({
      kind: "goto_page",
      page: 50,
    });
    expect(classifyChatCommand("open page twenty-one")).toEqual({
      kind: "goto_page",
      page: 21,
    });
    expect(classifyChatCommand("open page 0")).toEqual({
      kind: "goto_page",
      page: 0,
    });
  });

  it("leaves real questions on the RAG path", () => {
    expect(classifyChatCommand("what is on page 50").kind).toBe("question");
    expect(classifyChatCommand("what's on page 50").kind).toBe("question");
    expect(classifyChatCommand("summarize page 50").kind).toBe("question");
    expect(classifyChatCommand("open page 50 and tell me what it says").kind).toBe(
      "question"
    );
    expect(classifyChatCommand("what is content of week 4").kind).toBe("question");
    expect(classifyChatCommand("Schellingstrasse 50").kind).toBe("question");
    expect(classifyChatCommand("view the arguments on page 50").kind).toBe(
      "question"
    );
    expect(classifyChatCommand("where is page 50").kind).toBe("question");
    expect(classifyChatCommand("find week 4").kind).toBe("question");
  });

  it("opens a heading only when the user asked to move the PDF", () => {
    expect(classifyChatCommand("open week 4")).toEqual({
      kind: "goto_heading",
      query: "week 4",
    });
    expect(classifyChatCommand("show lecture 2")).toEqual({
      kind: "goto_heading",
      query: "lecture 2",
    });
    expect(classifyChatCommand("take me to week 4")).toEqual({
      kind: "goto_heading",
      query: "week 4",
    });
    expect(classifyChatCommand("view week 4")).toEqual({
      kind: "goto_heading",
      query: "week 4",
    });
    expect(classifyChatCommand("open chapter iv")).toEqual({
      kind: "goto_heading",
      query: "chapter 4",
    });
    expect(classifyChatCommand("week 4").kind).toBe("question");
  });

  it("handles panel and relative-page controls", () => {
    expect(classifyChatCommand("hide the pdf")).toEqual({ kind: "close_panel" });
    expect(classifyChatCommand("show the pdf")).toEqual({ kind: "open_panel" });
    expect(classifyChatCommand("open the file")).toEqual({ kind: "open_panel" });
    expect(classifyChatCommand("close the document")).toEqual({
      kind: "close_panel",
    });
    expect(classifyChatCommand("open the last page")).toEqual({ kind: "goto_last" });
    expect(classifyChatCommand("take me to the end")).toEqual({ kind: "goto_last" });
    expect(classifyChatCommand("go to the first page")).toEqual({
      kind: "goto_first",
    });
    expect(classifyChatCommand("next page")).toEqual({ kind: "goto_next" });
    expect(classifyChatCommand("go to next page")).toEqual({ kind: "goto_next" });
    expect(classifyChatCommand("open next page")).toEqual({ kind: "goto_next" });
    expect(classifyChatCommand("previous page")).toEqual({ kind: "goto_prev" });
    expect(classifyChatCommand("go to the previous page")).toEqual({
      kind: "goto_prev",
    });
  });

  it("answers small talk locally instead of searching", () => {
    expect(classifyChatCommand("hi")).toEqual({ kind: "social", reply: "greeting" });
    expect(classifyChatCommand("Hello!")).toEqual({ kind: "social", reply: "greeting" });
    expect(classifyChatCommand("heyy")).toEqual({ kind: "social", reply: "greeting" });
    expect(classifyChatCommand("good morning")).toEqual({
      kind: "social",
      reply: "greeting",
    });
    expect(classifyChatCommand("thanks!")).toEqual({ kind: "social", reply: "thanks" });
    expect(classifyChatCommand("thank you so much")).toEqual({
      kind: "social",
      reply: "thanks",
    });
    expect(classifyChatCommand("bye")).toEqual({ kind: "social", reply: "farewell" });
  });

  it("still searches when a greeting carries a real question", () => {
    expect(classifyChatCommand("hi, what is supervised learning").kind).toBe("question");
    expect(classifyChatCommand("hello can you summarize this").kind).toBe("question");
    expect(classifyChatCommand("what is a high five").kind).toBe("question");
    expect(classifyChatCommand("history of the treaty").kind).toBe("question");
  });

  it("keeps small talk out of the PDF-control path", () => {
    expect(isWorkspaceCommand("hi")).toBe(false);
    expect(isSocialMessage("hi")).toBe(true);
    expect(isSocialMessage("open page 4")).toBe(false);
  });
});
