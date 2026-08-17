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
    <div className="answer-markdown text-answer tracking-[-0.01em] text-ink-soft">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        rehypePlugins={[[rehypeSanitize, sanitizeSchema]]}
        components={{
          h1: ({ children }) => (
            <h1 className="mb-2 mt-4 text-h2 font-semibold tracking-[-0.02em] text-ink first:mt-0">
              {children}
            </h1>
          ),
          h2: ({ children }) => (
            <h2 className="mb-2 mt-4 text-title font-semibold tracking-[-0.01em] text-ink first:mt-0">
              {children}
            </h2>
          ),
          h3: ({ children }) => (
            <h3 className="mb-1.5 mt-3 text-answer font-semibold text-ink first:mt-0">
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
            <strong className="font-semibold text-ink">{children}</strong>
          ),
          em: ({ children }) => <em className="italic">{children}</em>,
          a: ({ href, children }) => (
            <a
              href={href}
              target="_blank"
              rel="noopener noreferrer"
              className="font-medium text-olive underline decoration-sage-soft underline-offset-2 hover:text-olive-dark"
            >
              {children}
            </a>
          ),
          blockquote: ({ children }) => (
            <blockquote className="mb-3 border-l-2 border-sage pl-3 text-ink-muted last:mb-0">
              {children}
            </blockquote>
          ),
          code: ({ className, children, ...props }) => {
            const isBlock = Boolean(className);

            if (!isBlock) {
              return (
                <code
                  className="rounded bg-surface-sunken px-1 py-0.5 font-mono text-meta text-olive-dark"
                  {...props}
                >
                  {children}
                </code>
              );
            }

            return (
              <code className={`font-mono text-meta ${className || ""}`} {...props}>
                {children}
              </code>
            );
          },
          pre: ({ children }) => (
            <pre className="mb-3 overflow-x-auto rounded-lg bg-surface-sunken p-3 text-meta last:mb-0">
              {children}
            </pre>
          ),
          table: ({ children }) => (
            <div className="mb-3 overflow-x-auto last:mb-0">
              <table className="w-full border-collapse text-ui">{children}</table>
            </div>
          ),
          thead: ({ children }) => (
            <thead className="bg-surface-sunken text-left text-ink">{children}</thead>
          ),
          th: ({ children }) => (
            <th className="border border-line px-2.5 py-1.5 font-semibold">{children}</th>
          ),
          td: ({ children }) => (
            <td className="border border-line px-2.5 py-1.5 align-top">{children}</td>
          ),
          hr: () => <hr className="my-4 border-line" />,
        }}
      >
        {content}
      </ReactMarkdown>
    </div>
  );
}
