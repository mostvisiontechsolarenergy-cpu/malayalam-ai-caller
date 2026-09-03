"use client";

import { useCallback, useState } from "react";

import { useSession } from "@/components/admin-shell";
import { apiRequest } from "@/lib/api";

type CallReportData = {
  id: string;
  client_name: string;
  client_phone: string;
  agent_name: string;
  status: string;
  attended: boolean;
  duration_seconds: number;
  duration_formatted: string;
  started_at: string;
  summary: string;
  customer_request: string;
};

type ReportResponse = {
  period: {
    start: string;
    end: string;
  };
  summary: {
    total_calls: number;
    completed_calls: number;
    missed_calls: number;
    total_duration_seconds: number;
    total_duration_formatted: string;
    avg_duration_seconds: number;
  };
  calls: CallReportData[];
};

function formatDuration(seconds: number): string {
  const minutes = Math.floor(seconds / 60);
  const secs = seconds % 60;
  if (minutes > 0) {
    return `${minutes}m ${secs}s`;
  }
  return `${secs}s`;
}

export default function CallReportsPage() {
  const session = useSession();
  const [startDate, setStartDate] = useState(() => {
    const lastWeek = new Date();
    lastWeek.setDate(lastWeek.getDate() - 7);
    return lastWeek.toISOString().split("T")[0];
  });
  const [endDate, setEndDate] = useState(() => {
    const today = new Date();
    return today.toISOString().split("T")[0];
  });
  const [report, setReport] = useState<ReportResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [downloading, setDownloading] = useState<"pdf" | "excel" | null>(null);
  const [error, setError] = useState("");

  const fetchReport = useCallback(async () => {
    setLoading(true);
    setError("");
    setReport(null);
    try {
      const data = await apiRequest<ReportResponse>(
        `backend/reports/call-summary?start_date=${startDate}&end_date=${endDate}`
      );
      setReport(data);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Unable to load report");
    } finally {
      setLoading(false);
    }
  }, [startDate, endDate]);

  const downloadFile = useCallback(
    async (format: "pdf" | "excel") => {
      setDownloading(format);
      setError("");
      try {
        const url = `/api/backend/reports/call-summary/${format}?start_date=${startDate}&end_date=${endDate}`;
        const response = await fetch(url, {
          credentials: "include",
        });
        if (!response.ok) {
          throw new Error("Download failed");
        }
        const blob = await response.blob();
        const downloadUrl = window.URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = downloadUrl;
        a.download = `call-report-${startDate}-to-${endDate}.${format === "pdf" ? "pdf" : "xlsx"}`;
        document.body.appendChild(a);
        a.click();
        window.URL.revokeObjectURL(downloadUrl);
        document.body.removeChild(a);
      } catch (caught) {
        setError(caught instanceof Error ? caught.message : "Unable to download report");
      } finally {
        setDownloading(null);
      }
    },
    [startDate, endDate]
  );

  return (
    <>
      <div className="page-heading">
        <div>
          <span className="eyebrow">Call analytics</span>
          <h1>Daily Call Summary Report</h1>
          <p>View and download call reports with details, summaries, and agent information.</p>
        </div>
      </div>

      {error ? <div className="form-error page-alert">{error}</div> : null}

      <section className="panel report-controls">
        <div className="report-date-row">
          <label className="field-label">
            From Date
            <input
              type="date"
              value={startDate}
              onChange={(e) => setStartDate(e.target.value)}
              max={endDate}
            />
          </label>
          <label className="field-label">
            To Date
            <input
              type="date"
              value={endDate}
              onChange={(e) => setEndDate(e.target.value)}
              min={startDate}
            />
          </label>
          <button
            className="primary-button"
            onClick={fetchReport}
            disabled={loading || !startDate || !endDate}
          >
            {loading ? "Loading..." : "Generate Report"}
          </button>
        </div>

        {report && (
          <div className="report-download-row">
            <button
              className="secondary-button"
              onClick={() => downloadFile("pdf")}
              disabled={downloading === "pdf" || report.calls.length === 0}
            >
              {downloading === "pdf" ? "Generating..." : "Download PDF"}
            </button>
            <button
              className="secondary-button"
              onClick={() => downloadFile("excel")}
              disabled={downloading === "excel" || report.calls.length === 0}
            >
              {downloading === "excel" ? "Generating..." : "Download Excel"}
            </button>
          </div>
        )}
      </section>

      {report && (
        <>
          <section className="panel report-summary">
            <h2>Summary</h2>
            <div className="report-stats-grid">
              <div className="report-stat-card">
                <span className="stat-value">{report.summary.total_calls}</span>
                <span className="stat-label">Total Calls</span>
              </div>
              <div className="report-stat-card">
                <span className="stat-value">{report.summary.completed_calls}</span>
                <span className="stat-label">Completed</span>
              </div>
              <div className="report-stat-card">
                <span className="stat-value">{report.summary.missed_calls}</span>
                <span className="stat-label">Missed/Failed</span>
              </div>
              <div className="report-stat-card">
                <span className="stat-value">{report.summary.total_duration_formatted}</span>
                <span className="stat-label">Total Duration</span>
              </div>
            </div>
          </section>

          <section className="data-card report-table-card">
            <div className="table-toolbar">
              <div>
                <strong>Call Details</strong>
                <span>
                  {report.calls.length} calls from {report.period.start} to {report.period.end}
                </span>
              </div>
            </div>
            <div className="table-scroll">
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Phone Number</th>
                    <th>Agent</th>
                    <th>Attended</th>
                    <th>Duration</th>
                    <th>Summary</th>
                    <th>Customer Request</th>
                  </tr>
                </thead>
                <tbody>
                  {report.calls.map((call) => (
                    <tr key={call.id}>
                      <td className="primary-cell">
                        <strong>{call.client_name}</strong>
                        <span>{call.client_phone}</span>
                      </td>
                      <td>{call.agent_name}</td>
                      <td>
                        <span
                          className={`status-badge ${
                            call.attended ? "success" : "warning"
                          }`}
                        >
                          {call.attended ? "Yes" : "No"}
                        </span>
                      </td>
                      <td>{call.duration_formatted}</td>
                      <td className="summary-cell">
                        {call.summary || "—"}
                      </td>
                      <td className="summary-cell">
                        {call.customer_request || "—"}
                      </td>
                    </tr>
                  ))}
                  {!loading && report.calls.length === 0 ? (
                    <tr>
                      <td colSpan={6}>
                        <div className="compact-empty">
                          <h3>No calls in this period</h3>
                          <p>Try selecting a different date range.</p>
                        </div>
                      </td>
                    </tr>
                  ) : null}
                </tbody>
              </table>
            </div>
          </section>
        </>
      )}

      {!report && !loading && (
        <section className="panel report-empty">
          <div className="compact-empty">
            <h3>Select dates and generate report</h3>
            <p>Choose a date range above and click &quot;Generate Report&quot; to view call details.</p>
          </div>
        </section>
      )}
    </>
  );
}
