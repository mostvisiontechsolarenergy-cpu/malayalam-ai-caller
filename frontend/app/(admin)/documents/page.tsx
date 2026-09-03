"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { StatusBadge, formatDate } from "@/components/resource-page";
import { useSession } from "@/components/admin-shell";
import { apiRequest } from "@/lib/api";

type DocumentRecord = {
  id: string;
  filename: string;
  file_type: string;
  size_bytes: number;
  status: "UPLOADING" | "PROCESSING" | "READY" | "FAILED";
  embedding_status: string;
  error_message: string | null;
  chunk_count: number;
  created_at: string;
};

function messageFrom(payload: unknown) {
  if (payload && typeof payload === "object" && "detail" in payload) {
    return String((payload as { detail: unknown }).detail);
  }
  return "The document could not be uploaded.";
}

export default function DocumentsPage() {
  const { user } = useSession();
  const canManage = user.role !== "STAFF";
  const input = useRef<HTMLInputElement>(null);
  const [documents, setDocuments] = useState<DocumentRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [dragging, setDragging] = useState(false);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    try {
      setDocuments(await apiRequest<DocumentRecord[]>("backend/documents"));
      setError("");
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Could not load documents.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
    const timer = window.setInterval(() => void load(), 4000);
    return () => window.clearInterval(timer);
  }, [load]);

  async function upload(file?: File) {
    if (!file || !canManage) return;
    const body = new FormData();
    body.append("file", file);
    setUploading(true);
    setError("");
    try {
      const response = await fetch("/api/backend/documents", { method: "POST", body });
      const payload = await response.json();
      if (!response.ok) throw new Error(messageFrom(payload));
      await load();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Upload failed.");
    } finally {
      setUploading(false);
      if (input.current) input.current.value = "";
    }
  }

  async function reprocess(id: string) {
    try {
      await apiRequest(`backend/documents/${id}/reprocess`, { method: "POST" });
      await load();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Reprocessing failed.");
    }
  }

  async function remove(id: string) {
    if (!window.confirm("Delete this document and all of its searchable chunks?")) return;
    try {
      await apiRequest(`backend/documents/${id}`, { method: "DELETE" });
      await load();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Delete failed.");
    }
  }

  return (
    <>
      <header className="page-heading">
        <div>
          <span className="eyebrow">Phase 3 · Knowledge ingestion</span>
          <h1>Documents</h1>
          <p>Upload approved company knowledge. Text is extracted, chunked, source-tracked, and made searchable without exposing the original file publicly.</p>
        </div>
      </header>
      <div className="info-banner"><strong>Secure search:</strong> Every processed document remains searchable through the configured private knowledge index.</div>
      {error && <div className="form-error page-alert">{error}</div>}
      {canManage && (
        <section
          className={`upload-zone ${dragging ? "dragging" : ""}`}
          onDragOver={(event) => { event.preventDefault(); setDragging(true); }}
          onDragLeave={() => setDragging(false)}
          onDrop={(event) => { event.preventDefault(); setDragging(false); void upload(event.dataTransfer.files[0]); }}
        >
          <div className="upload-mark">↑</div>
          <h2>Drop a knowledge document here</h2>
          <p>PDF, DOCX, TXT, CSV, or XLSX · maximum 15 MB</p>
          <button className="primary-button" disabled={uploading} onClick={() => input.current?.click()}>
            {uploading ? "Uploading…" : "Choose document"}
          </button>
          <input ref={input} hidden type="file" accept=".pdf,.docx,.txt,.csv,.xlsx" onChange={(event) => void upload(event.target.files?.[0])} />
        </section>
      )}
      <section className="data-card knowledge-table-card">
        <div className="table-toolbar"><div><strong>Knowledge documents</strong><span>{documents.length} uploaded file{documents.length === 1 ? "" : "s"}</span></div></div>
        {loading ? <div className="table-state">Loading documents…</div> : documents.length === 0 ? (
          <div className="empty-state"><div className="empty-mark">D</div><h3>No documents yet</h3><p>Upload your first approved knowledge file above.</p></div>
        ) : (
          <div className="table-scroll"><table className="data-table"><thead><tr><th>Document</th><th>Processing</th><th>Search</th><th>Chunks</th><th>Uploaded</th><th className="actions-column">Actions</th></tr></thead><tbody>
            {documents.map((document) => <tr key={document.id}>
              <td><div className="primary-cell"><strong>{document.filename}</strong><span>{(document.size_bytes / 1024).toFixed(1)} KB · {document.file_type.slice(1).toUpperCase()}</span>{document.error_message && <span className="error-copy">{document.error_message}</span>}</div></td>
              <td><StatusBadge tone={document.status === "READY" ? "success" : document.status === "FAILED" ? "danger" : "warning"}>{document.status}</StatusBadge></td>
              <td><StatusBadge tone={document.embedding_status === "READY" ? "success" : document.embedding_status === "FAILED" ? "danger" : "info"}>{document.embedding_status.replaceAll("_", " ")}</StatusBadge></td>
              <td>{document.chunk_count}</td><td>{formatDate(document.created_at)}</td>
              <td className="row-actions"><a href={`/api/backend/documents/${document.id}/download`}>Download</a>{canManage && <><button onClick={() => void reprocess(document.id)}>Reprocess</button><button className="danger-link" onClick={() => void remove(document.id)}>Delete</button></>}</td>
            </tr>)}
          </tbody></table></div>
        )}
      </section>
    </>
  );
}
