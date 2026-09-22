import type { Metadata } from "next";
import { SiteShell } from "@/components/site/SiteChrome";

export const metadata: Metadata = {
  title: "Privacy — DocuSage",
  description: "How DocuSage handles your PDFs, chats, and Google sign-in.",
};

export default function PrivacyPage() {
  return (
    <SiteShell>
      <article className="max-w-2xl">
        <h1 className="text-h1 font-semibold tracking-[-0.02em] text-ink">Privacy</h1>
        <p className="mt-2 text-meta text-ink-subtle">Last updated 8 September 2026</p>
        <p className="mt-6 text-body leading-relaxed text-ink-muted">
          DocuSage is a document assistant. You upload PDFs and ask questions.
          Answers are generated from those files. This page describes what we
          store so we can do that. It is not legal advice.
        </p>

        <h2 className="mt-8 text-title font-semibold text-ink">What you upload</h2>
        <p className="mt-2 text-body leading-relaxed text-ink-muted">
          PDF files you add are sent to the DocuSage API so they can be extracted,
          indexed, and used to answer questions. Passages from those files may be
          shown as citations, quotes, and page highlights in the workspace.
        </p>

        <h2 className="mt-8 text-title font-semibold text-ink">Guest use</h2>
        <p className="mt-2 text-body leading-relaxed text-ink-muted">
          If you do not sign in, the app keeps a guest session id in your browser
          so your trial uploads and chats stay on this device. Clearing site data
          or switching browsers starts a new guest session. Guest files are
          limited and are not a permanent archive.
        </p>

        <h2 className="mt-8 text-title font-semibold text-ink">Signed-in accounts</h2>
        <p className="mt-2 text-body leading-relaxed text-ink-muted">
          Sign-in uses Google through Supabase. We receive the account identifier
          Google provides (typically email, name, and photo if you allow them) so
          we can attach your documents and conversations to your account. We do
          not use your PDFs to train public models.
        </p>

        <h2 className="mt-8 text-title font-semibold text-ink">What we do not do</h2>
        <p className="mt-2 text-body leading-relaxed text-ink-muted">
          We do not sell your documents or chat history. We do not show ads based
          on your files. Operators of this deployment can see data needed to run
          the service (for example logs and stored files) and should treat it as
          private.
        </p>

        <h2 className="mt-8 text-title font-semibold text-ink">Questions</h2>
        <p className="mt-2 text-body leading-relaxed text-ink-muted">
          This is an independent beta. If you need a file removed from a
          deployment you control, delete it in the workspace. For the public
          project, open an issue on the GitHub repository for this app.
        </p>
      </article>
    </SiteShell>
  );
}
