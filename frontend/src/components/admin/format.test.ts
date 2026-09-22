import { describe, expect, it } from "vitest";

import { countryName, kindLabel, providerLabel } from "./format";

describe("providerLabel", () => {
  it("names the models the operator dashboard should show", () => {
    expect(providerLabel("groq")).toBe("Groq");
    expect(providerLabel("gemini")).toBe("Gemini");
    expect(providerLabel("cerebras")).toBe("Cerebras");
    expect(providerLabel("openrouter")).toBe("OpenRouter");
    expect(providerLabel("mistral")).toBe("Mistral");
    expect(providerLabel("ollama")).toBe("Ollama");
  });
});

describe("kindLabel", () => {
  it("labels answered and unanswered events", () => {
    expect(kindLabel("answer")).toBe("Answered");
    expect(kindLabel("unanswered")).toBe("Couldn't answer");
  });
});

describe("countryName", () => {
  it("expands ISO country codes", () => {
    expect(countryName("PK")).toBe("Pakistan");
    expect(countryName(null)).toBe("Unknown");
  });
});
