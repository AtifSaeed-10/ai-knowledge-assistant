"use client";

import React from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import rehypeSanitize, { defaultSchema } from "rehype-sanitize";

const sanitizeSchema = {
  ...defaultSchema,
  tagNames: [
    ...(defaultSchema.tagNames || []),
    "table",
    "thead",
    "tbody",
    "tfoot",
    "tr",
    "th",
    "td",
  ],
  attributes: {
    ...defaultSchema.attributes,
    code: [...((defaultSchema.attributes?.code as string[]) || []), "className"],
    pre: [...((defaultSchema.attributes?.pre as string[]) || []), "className"],
    th: ["align"],
    td: ["align"],
    a: ["href", "title", "rel", "target"],
  },
};

export function AnswerMarkdown({ content }: { content: string }) {
  if (!content.trim()) return null;

  return (
    <div className="answer-markdown text-[15px] leading-[1.65] tracking-[-0.01em] text-[#2A322E]">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        rehypePlugins={[[rehypeSanitize, sanitizeSchema]]}
        components={{
          h1: ({ children }) => (
            <h1 className="mb-2 mt-4 text-[18px] font-semibold tracking-[-0.02em] text-[#1C241F] first:mt-0">
              {children}
            </h1>
          ),
          h2: ({ children }) => (
            <h2 className="mb-2 mt-4 text-[16px] font-semibold tracking-[-0.01em] text-[#1C241F] first:mt-0">
              {children}
            </h2>
          ),
          h3: ({ children }) => (
            <h3 className="mb-1.5 mt-3 text-[15px] font-semibold text-[#1C241F] first:mt-0">
              {children}
            </h3>
          ),
          p: ({ children }) => <p className="mb-3 last:mb-0">{children}</p>,
          ul: ({ children }) => (
            <ul className="mb-3 list-disc space-y-1 pl-5 last:mb-0">{children}</ul>
          ),
          ol: ({ children }) => (
            <ol className="mb-3 list-decimal space-y-1 pl-5 last:mb-0">{children}</ol>
          ),
          li: ({ children }) => <li className="pl-0.5">{children}</li>,
          strong: ({ children }) => (
            <strong className="font-semibold text-[#1C241F]">{children}</strong>
          ),
          em: ({ children }) => <em className="italic">{children}</em>,
          a: ({ href, children }) => (
            <a
              href={href}
              target="_blank"
              rel="noopener noreferrer"
              className="font-medium text-[#4A5D23] underline decoration-[#C5D4B8] underline-offset-2 hover:text-[#3E4E1D]"
            >
              {children}
            </a>
          ),
          blockquote: ({ children }) => (
            <blockquote className="mb-3 border-l-2 border-[#87AB72] pl-3 text-[#5B6858]">
              {children}
            </blockquote>
          ),
          code: ({ className, children, ...props }) => {
            const isBlock = Boolean(className);
            if (!isBlock) {
              return (
                <code
                  className="rounded bg-[#F1F3EF] px-1 py-0.5 font-mono text-[13px] text-[#3E4E1D]"
                  {...props}
                >
                  {children}
                </code>
              );
            }
            return (
              <code className={`font-mono text-[12.5px] ${className || ""}`} {...props}>
                {children}
              </code>
            );
          },
          pre: ({ children }) => (
            <pre className="mb-3 overflow-x-auto rounded-lg bg-[#F1F3EF] p-3 text-[12.5px] last:mb-0">
              {children}
            </pre>
          ),
          table: ({ children }) => (
            <div className="mb-3 overflow-x-auto last:mb-0">
              <table className="w-full border-collapse text-[13px]">{children}</table>
            </div>
          ),
          thead: ({ children }) => (
            <thead className="bg-[#F6F7F4] text-left text-[#1C241F]">{children}</thead>
          ),
          th: ({ children }) => (
            <th className="border border-[#EBEFEA] px-2.5 py-1.5 font-semibold">{children}</th>
          ),
          td: ({ children }) => (
            <td className="border border-[#EBEFEA] px-2.5 py-1.5">{children}</td>
          ),
          hr: () => <hr className="my-4 border-[#EBEFEA]" />,
        }}
      >
        {content}
      </ReactMarkdown>
    </div>
  );
}
