import type { Metadata } from "next";
import { SiteShell } from "@/components/site/SiteChrome";

export const metadata: Metadata = {
  title: "Terms — DocuSage",
  description: "Terms for using the DocuSage beta.",
};

export default function TermsPage() {
  return (
    <SiteShell>
      <article className="max-w-2xl">
        <h1 className="text-h1 font-semibold tracking-[-0.02em] text-ink">Terms</h1>
        <p className="mt-2 text-meta text-ink-subtle">Last updated 8 September 2026</p>
        <p className="mt-6 text-body leading-relaxed text-ink-muted">
          DocuSage is a beta. Use it to ask questions about PDFs you have the
          right to upload. These terms are a plain-language notice, not a
          contract drafted by a lawyer.
        </p>

        <h2 className="mt-8 text-title font-semibold text-ink">The product</h2>
        <p className="mt-2 text-body leading-relaxed text-ink-muted">
          The app indexes your documents and answers from that text. Citations
          point at pages. The model can still be wrong or incomplete. Always
          open the cited page before you rely on an answer.
        </p>

        <h2 className="mt-8 text-title font-semibold text-ink">Your files</h2>
        <p className="mt-2 text-body leading-relaxed text-ink-muted">
          Only upload documents you are allowed to process. Do not upload
          secrets you cannot store with a third-party host. Guest trials are
          limited. Signing in with Google is optional and still free at the
          published limits.
        </p>

        <h2 className="mt-8 text-title font-semibold text-ink">Availability</h2>
        <p className="mt-2 text-body leading-relaxed text-ink-muted">
          The service may change, break, or stop. There is no warranty and no
          promise of uptime, accuracy, or fitness for a particular purpose.
        </p>
      </article>
    </SiteShell>
  );
}
