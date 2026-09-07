import { describe, expect, it } from "vitest";

import { pageTextMatchesHeading } from "./findHeadingPage";

describe("pageTextMatchesHeading", () => {
  it("matches common syllabus heading spellings", () => {
    expect(pageTextMatchesHeading("Week 4: Neural Networks", "week 4")).toBe(
      true
    );
    expect(pageTextMatchesHeading("WEEK4 LAB", "week 4")).toBe(true);
    expect(pageTextMatchesHeading("Lecture 2 Overview", "lecture 2")).toBe(true);
    expect(pageTextMatchesHeading("Week Four: Review", "week 4")).toBe(true);
    expect(pageTextMatchesHeading("Chapter IV", "chapter 4")).toBe(true);
  });

  it("does not treat an address number as a week heading", () => {
    expect(pageTextMatchesHeading("Schellingstrasse 50.", "week 4")).toBe(false);
    expect(pageTextMatchesHeading("Schellingstrasse 50.", "page 50")).toBe(
      false
    );
  });
});
