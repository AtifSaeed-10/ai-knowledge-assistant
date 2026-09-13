import type { Metadata } from "next";
import { SiteShell } from "@/components/site/SiteChrome";

export const metadata: Metadata = {
  title: "About — DocuSage",
  description: "What DocuSage is and who it is for.",
};

export default function AboutPage() {
  return (
    <SiteShell>
      <article className="max-w-2xl">
        <h1 className="text-h1 font-semibold tracking-[-0.02em] text-ink">About</h1>
        <p className="mt-2 text-meta text-ink-subtle">A free PDF research assistant for students</p>
        <p className="mt-6 text-body leading-relaxed text-ink-muted">
          DocuSage answers questions from the PDFs you upload. Every important
          claim in an answer is meant to carry a citation you can open — the
          source page, with the sentence highlighted.
        </p>

        <h2 className="mt-8 text-title font-semibold text-ink">How it works</h2>
        <p className="mt-2 text-body leading-relaxed text-ink-muted">
          You add a document. The app indexes it, then answers from that text.
          If the files do not support an answer, it should say so rather than
          guess. You can try one PDF and a short question allowance without an
          account. Signing in with Google is free and saves your work.
        </p>

        <h2 className="mt-8 text-title font-semibold text-ink">What we do not do</h2>
        <p className="mt-2 text-body leading-relaxed text-ink-muted">
          There is no paid tier in this beta, and we do not use your PDFs to
          train public models. Read{" "}
          <a href="/privacy" className="font-medium text-olive hover:text-olive-dark">
            Privacy
          </a>{" "}
          and{" "}
          <a href="/terms" className="font-medium text-olive hover:text-olive-dark">
            Terms
          </a>{" "}
          for the details.
        </p>
      </article>
    </SiteShell>
  );
}
