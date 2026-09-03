"use client";

import {
  FormEvent,
  useCallback,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";

import { apiRequest, type ApiRecord } from "@/lib/api";
import { useSession } from "@/components/admin-shell";

export type FieldOption = { label: string; value: string };
export type FieldConfig = {
  name: string;
  label: string;
  type?: "text" | "email" | "tel" | "textarea" | "select" | "checkbox" | "date" | "number" | "tags";
  required?: boolean;
  placeholder?: string;
  help?: string;
  options?: FieldOption[];
  lookup?: { endpoint: string; labelKey: string; placeholder: string };
  min?: number;
  max?: number;
  step?: string;
  wide?: boolean;
};

export type LookupStore = Record<string, ApiRecord[]>;
export type ColumnConfig = {
  label: string;
  render: (record: ApiRecord, lookups: LookupStore) => ReactNode;
};

type ResourcePageProps = {
  title: string;
  description: string;
  singular: string;
  endpoint: string;
  fields: FieldConfig[];
  columns: ColumnConfig[];
  initialValues?: Record<string, unknown>;
  validate?: (payload: Record<string, unknown>) => string | null;
  note?: ReactNode;
};

export function StatusBadge({ children, tone = "neutral" }: { children: ReactNode; tone?: "success" | "warning" | "danger" | "neutral" | "info" }) {
  return <span className={`status-badge ${tone}`}>{children}</span>;
}

export function formatCurrency(value: unknown, currency = "INR") {
  const numeric = Number(value);
  if (!Number.isFinite(numeric)) return "—";
  return new Intl.NumberFormat("en-IN", {
    style: "currency",
    currency,
    maximumFractionDigits: 2,
  }).format(numeric);
}

export function formatDate(value: unknown) {
  if (!value) return "—";
  const date = new Date(String(value));
  if (Number.isNaN(date.valueOf())) return String(value);
  return new Intl.DateTimeFormat("en-IN", { day: "2-digit", month: "short", year: "numeric" }).format(date);
}

export function truncate(value: unknown, length = 70) {
  if (!value) return "—";
  const text = String(value);
  return text.length > length ? `${text.slice(0, length)}…` : text;
}

function valueForField(field: FieldConfig, record?: ApiRecord, initialValues?: Record<string, unknown>) {
  const source = record?.[field.name] ?? initialValues?.[field.name];
  if (field.type === "checkbox") return Boolean(source);
  if (field.type === "tags") return Array.isArray(source) ? source.join(", ") : source ?? "";
  return source ?? "";
}

function buildFormState(
  fields: FieldConfig[],
  record?: ApiRecord,
  initialValues?: Record<string, unknown>,
) {
  return Object.fromEntries(
    fields.map((field) => [field.name, valueForField(field, record, initialValues)]),
  );
}

function normalizePayload(fields: FieldConfig[], state: Record<string, unknown>) {
  return Object.fromEntries(
    fields.map((field) => {
      const value = state[field.name];
      if (field.type === "checkbox") return [field.name, Boolean(value)];
      if (field.type === "number") {
        return [field.name, value === "" || value === null ? null : Number(value)];
      }
      if (field.type === "tags") {
        const tags = String(value ?? "")
          .split(",")
          .map((item) => item.trim())
          .filter(Boolean);
        return [field.name, tags];
      }
      if (value === "" && !field.required) return [field.name, null];
      return [field.name, value];
    }),
  );
}

export default function ResourcePage({
  title,
  description,
  singular,
  endpoint,
  fields,
  columns,
  initialValues,
  validate,
  note,
}: ResourcePageProps) {
  const session = useSession();
  const canWrite = session.user.role !== "STAFF";
  const [records, setRecords] = useState<ApiRecord[]>([]);
  const [lookups, setLookups] = useState<LookupStore>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [search, setSearch] = useState("");
  const [editing, setEditing] = useState<ApiRecord | null>(null);
  const [formOpen, setFormOpen] = useState(false);
  const [formState, setFormState] = useState<Record<string, unknown>>(
    buildFormState(fields, undefined, initialValues),
  );
  const [saving, setSaving] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const lookupEndpoints = Array.from(
        new Set(fields.flatMap((field) => (field.lookup ? [field.lookup.endpoint] : []))),
      );
      const [items, lookupResults] = await Promise.all([
        apiRequest<ApiRecord[]>(`backend/${endpoint}?limit=100`),
        Promise.all(
          lookupEndpoints.map(async (lookupEndpoint) => [
            lookupEndpoint,
            await apiRequest<ApiRecord[]>(`backend/${lookupEndpoint}?limit=100`),
          ] as const),
        ),
      ]);
      setRecords(items);
      setLookups(Object.fromEntries(lookupResults));
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : `Unable to load ${title.toLowerCase()}`);
    } finally {
      setLoading(false);
    }
  }, [endpoint, fields, title]);

  useEffect(() => {
    void load();
  }, [load]);

  const filtered = useMemo(() => {
    const needle = search.trim().toLowerCase();
    if (!needle) return records;
    return records.filter((record) => JSON.stringify(record).toLowerCase().includes(needle));
  }, [records, search]);

  function openCreate() {
    setEditing(null);
    setFormState(buildFormState(fields, undefined, initialValues));
    setError("");
    setFormOpen(true);
  }

  function openEdit(record: ApiRecord) {
    setEditing(record);
    setFormState(buildFormState(fields, record, initialValues));
    setError("");
    setFormOpen(true);
  }

  async function submit(event: FormEvent) {
    event.preventDefault();
    const payload = normalizePayload(fields, formState);
    const validationError = validate?.(payload);
    if (validationError) {
      setError(validationError);
      return;
    }
    setSaving(true);
    setError("");
    try {
      await apiRequest(`backend/${endpoint}${editing ? `/${editing.id}` : ""}`, {
        method: editing ? "PATCH" : "POST",
        body: JSON.stringify(payload),
      });
      setFormOpen(false);
      setSuccess(`${singular} ${editing ? "updated" : "created"} successfully.`);
      window.setTimeout(() => setSuccess(""), 3500);
      await load();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : `Unable to save ${singular.toLowerCase()}`);
    } finally {
      setSaving(false);
    }
  }

  async function remove(record: ApiRecord) {
    const label = String(record.name ?? record.title ?? record.question ?? singular);
    if (!window.confirm(`Delete “${label}”? This cannot be undone.`)) return;
    setError("");
    try {
      await apiRequest(`backend/${endpoint}/${record.id}`, { method: "DELETE" });
      setSuccess(`${singular} deleted.`);
      window.setTimeout(() => setSuccess(""), 3500);
      await load();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : `Unable to delete ${singular.toLowerCase()}`);
    }
  }

  function fieldOptions(field: FieldConfig) {
    if (field.options) return field.options;
    if (!field.lookup) return [];
    return (lookups[field.lookup.endpoint] ?? []).map((record) => ({
      value: record.id,
      label: String(record[field.lookup!.labelKey] ?? record.id),
    }));
  }

  return (
    <>
      <div className="page-heading">
        <div>
          <span className="eyebrow">Company workspace</span>
          <h1>{title}</h1>
          <p>{description}</p>
        </div>
        {canWrite ? <button className="primary-button" onClick={openCreate}>+ Add {singular}</button> : null}
      </div>

      {note ? <div className="info-banner">{note}</div> : null}
      {error && !formOpen ? <div className="form-error page-alert" role="alert">{error}</div> : null}
      {success ? <div className="success-toast" role="status">✓ {success}</div> : null}

      <section className="data-card">
        <div className="table-toolbar">
          <div>
            <strong>{records.length} {records.length === 1 ? singular : title.toLowerCase()}</strong>
            <span>Live company records</span>
          </div>
          <label className="search-box">
            <span>⌕</span>
            <input
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              placeholder={`Search ${title.toLowerCase()}…`}
              aria-label={`Search ${title}`}
            />
          </label>
        </div>

        {loading ? (
          <div className="table-state"><div className="loading-line" /><p>Loading live records…</p></div>
        ) : filtered.length === 0 ? (
          <div className="empty-state">
            <div className="empty-mark">{search ? "⌕" : "+"}</div>
            <h2>{search ? "No matching records" : `No ${title.toLowerCase()} yet`}</h2>
            <p>{search ? "Try a different search term." : `Add your first ${singular.toLowerCase()} to begin.`}</p>
            {!search && canWrite ? <button className="secondary-button" onClick={openCreate}>Add {singular}</button> : null}
          </div>
        ) : (
          <div className="table-scroll">
            <table className="data-table">
              <thead>
                <tr>
                  {columns.map((column) => <th key={column.label}>{column.label}</th>)}
                  {canWrite ? <th className="actions-column">Actions</th> : null}
                </tr>
              </thead>
              <tbody>
                {filtered.map((record) => (
                  <tr key={record.id}>
                    {columns.map((column) => <td key={column.label}>{column.render(record, lookups)}</td>)}
                    {canWrite ? (
                      <td className="row-actions">
                        <button onClick={() => openEdit(record)}>Edit</button>
                        <button className="danger-link" onClick={() => remove(record)}>Delete</button>
                      </td>
                    ) : null}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      {formOpen ? (
        <div className="modal-backdrop" role="presentation" onMouseDown={(event) => {
          if (event.currentTarget === event.target) setFormOpen(false);
        }}>
          <section className="modal-card" role="dialog" aria-modal="true" aria-labelledby="resource-form-title">
            <div className="modal-header">
              <div>
                <span className="eyebrow">{editing ? "Update record" : "New record"}</span>
                <h2 id="resource-form-title">{editing ? `Edit ${singular}` : `Add ${singular}`}</h2>
              </div>
              <button className="icon-button" onClick={() => setFormOpen(false)} aria-label="Close form">×</button>
            </div>
            <form onSubmit={submit}>
              <div className="form-grid">
                {fields.map((field) => {
                  const value = formState[field.name];
                  const shared = {
                    id: `field-${field.name}`,
                    name: field.name,
                    required: field.required,
                    value: String(value ?? ""),
                    onChange: (event: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) =>
                      setFormState((current) => ({ ...current, [field.name]: event.target.value })),
                  };
                  return (
                    <label className={`field-label ${field.wide ? "wide" : ""} ${field.type === "checkbox" ? "checkbox-field" : ""}`} key={field.name} htmlFor={shared.id}>
                      {field.type === "checkbox" ? (
                        <>
                          <input
                            id={shared.id}
                            name={field.name}
                            type="checkbox"
                            checked={Boolean(value)}
                            onChange={(event) => setFormState((current) => ({ ...current, [field.name]: event.target.checked }))}
                          />
                          <span><strong>{field.label}</strong>{field.help ? <small>{field.help}</small> : null}</span>
                        </>
                      ) : (
                        <>
                          <span>{field.label}{field.required ? <em> *</em> : null}</span>
                          {field.type === "textarea" ? (
                            <textarea {...shared} placeholder={field.placeholder} rows={4} />
                          ) : field.type === "select" ? (
                            <select {...shared}>
                              <option value="">{field.lookup?.placeholder ?? `Select ${field.label.toLowerCase()}`}</option>
                              {fieldOptions(field).map((option) => <option value={option.value} key={option.value}>{option.label}</option>)}
                            </select>
                          ) : (
                            <input
                              {...shared}
                              type={field.type === "tags" ? "text" : field.type ?? "text"}
                              placeholder={field.placeholder}
                              min={field.min}
                              max={field.max}
                              step={field.step}
                            />
                          )}
                          {field.help ? <small>{field.help}</small> : null}
                        </>
                      )}
                    </label>
                  );
                })}
              </div>
              {error ? <div className="form-error" role="alert">{error}</div> : null}
              <div className="modal-actions">
                <button type="button" className="secondary-button" onClick={() => setFormOpen(false)}>Cancel</button>
                <button className="primary-button" disabled={saving}>{saving ? "Saving…" : `Save ${singular}`}</button>
              </div>
            </form>
          </section>
        </div>
      ) : null}
    </>
  );
}
