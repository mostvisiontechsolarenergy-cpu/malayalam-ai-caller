"use client";

import ResourcePage, { StatusBadge, formatDate, truncate, type FieldConfig } from "@/components/resource-page";

const categories = ["Company Details", "About Company", "Products", "Services", "Pricing", "Packages", "Offers", "FAQs", "Policies", "Locations", "Service Areas", "Delivery Information", "Payment Information", "Warranty", "Support Information", "Sales Information", "Custom Knowledge"];

const fields: FieldConfig[] = [
  { name: "title", label: "Knowledge title", required: true, placeholder: "Working hours" },
  { name: "category", label: "Category", type: "select", required: true, options: categories.map((value) => ({ label: value, value })) },
  { name: "content", label: "Approved knowledge", type: "textarea", required: true, wide: true, placeholder: "Enter the exact company information the AI may use" },
  { name: "keywords", label: "Keywords", type: "tags", wide: true, placeholder: "hours, timing, open", help: "Separate search terms with commas." },
  { name: "language", label: "Language", type: "select", required: true, options: [{ label: "Malayalam", value: "ml" }, { label: "English", value: "en" }, { label: "Malayalam + English", value: "ml-en" }] },
  { name: "priority", label: "Priority", type: "number", required: true, min: 0, max: 100, help: "Higher-priority records are considered first." },
  { name: "valid_from", label: "Valid from", type: "date" },
  { name: "valid_until", label: "Valid until", type: "date" },
  { name: "internal_notes", label: "Internal notes", type: "textarea", wide: true, placeholder: "Not shared with customers" },
  { name: "active", label: "Active knowledge", type: "checkbox", help: "Inactive or expired knowledge is excluded from retrieval." },
];

export default function KnowledgePage() {
  return <ResourcePage
    title="Knowledge Base"
    singular="Knowledge item"
    endpoint="knowledge-items"
    description="Teach the AI approved company facts without changing application code."
    note={<><strong>Phase 3 is live:</strong> manual records now participate in hybrid retrieval alongside catalog data, FAQs, and uploaded documents. Structured prices and offers remain authoritative when sources conflict.</>}
    fields={fields}
    initialValues={{ category: "Company Details", language: "ml", priority: 50, active: true, keywords: [] }}
    validate={(payload) => payload.valid_from && payload.valid_until && String(payload.valid_until) < String(payload.valid_from) ? "Valid until cannot be earlier than valid from." : null}
    columns={[
      { label: "Knowledge", render: (record) => <div className="primary-cell"><strong>{String(record.title)}</strong><span>{truncate(record.content, 76)}</span></div> },
      { label: "Category", render: (record) => String(record.category) },
      { label: "Language", render: (record) => String(record.language).toUpperCase() },
      { label: "Priority", render: (record) => String(record.priority) },
      { label: "Valid until", render: (record) => formatDate(record.valid_until) },
      { label: "Status", render: (record) => <StatusBadge tone={record.active ? "success" : "neutral"}>{record.active ? "ACTIVE" : "INACTIVE"}</StatusBadge> },
    ]}
  />;
}
