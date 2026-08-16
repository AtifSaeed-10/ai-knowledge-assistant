import { ConversationSummary } from "@/types/conversation";
import { Message, Citation } from "@/types";

function citationLine(citation: Citation): string {
  const page = citation.pageNumber ? ` — p. ${citation.pageNumber}` : "";
  return `- ${citation.documentName}${page}`;
}

export function conversationToMarkdown(
  conversation: Pick<ConversationSummary, "title">,
  messages: Message[]
): string {
  const lines: string[] = [
    `# ${conversation.title || "Conversation"}`,
    "",
    `_Exported ${new Date().toISOString()}_`,
    "",
  ];

  for (const message of messages) {
    if (message.role === "user") {
      lines.push("## User", "", message.content.trim(), "");
    } else {
      lines.push("## DocuSage", "", message.content.trim(), "");
      if (message.citations && message.citations.length > 0) {
        lines.push("Citations:", "");
        for (const citation of message.citations) {
          lines.push(citationLine(citation));
        }
        lines.push("");
      }
    }
  }

  return lines.join("\n").trim() + "\n";
}

export function downloadTextFile(filename: string, content: string) {
  const blob = new Blob([content], { type: "text/markdown;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(url);
}

export function safeFilename(title: string): string {
  const compact = title.replace(/[<>:"/\\|?*]+/g, "").trim() || "conversation";
  return `${compact.slice(0, 40)}.md`;
}
