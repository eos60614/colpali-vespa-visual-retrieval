import { UploadForm } from "@/components/upload/upload-form";

export const metadata = {
  title: "Upload — KI55",
  description: "Upload PDF documents for indexing and search.",
};

export default function UploadPage() {
  return (
    <main className="min-h-screen bg-[var(--bg-primary)]">
      <div className="max-w-2xl mx-auto px-6 py-16">
        <div className="text-center mb-10">
          <div className="w-12 h-12 rounded-[var(--radius-xl)] bg-gradient-to-br from-[#d97756] to-[#b85636] flex items-center justify-center mx-auto mb-4">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" className="text-white">
              <path d="M12 2L2 7l10 5 10-5-10-5z" fill="currentColor" opacity="0.3" />
              <path d="M2 17l10 5 10-5" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
              <path d="M2 12l10 5 10-5" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
          </div>
          <h1 className="text-xl font-semibold text-[var(--text-primary)] mb-2">
            Upload Document
          </h1>
          <p className="text-sm text-[var(--text-tertiary)]">
            Upload a PDF to index it for visual search. The document will be
            processed, embedded, and made searchable.
          </p>
        </div>
        <UploadForm />
      </div>
    </main>
  );
}
