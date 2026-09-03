"use client";

import ResourcePage, { StatusBadge, formatDate, truncate, type FieldConfig } from "@/components/resource-page";

const fields: FieldConfig[] = [
  { name: "name", label: "Client name", required: true, placeholder: "Customer or contact name" },
  { name: "phone", label: "Primary phone", type: "tel", required: true, placeholder: "+91 98765 43210", help: "Indian numbers are normalized to international format." },
  { name: "alternative_phone", label: "Alternative phone", type: "tel", placeholder: "+91 98765 43210" },
  { name: "business_name", label: "Business name", placeholder: "Optional business" },
  { name: "email", label: "Email", type: "email", placeholder: "customer@example.com" },
  { name: "location", label: "Location", placeholder: "Kochi, Kerala" },
  { name: "preferred_language", label: "Preferred language", type: "select", required: true, options: [
    { label: "Malayalam", value: "ml" }, { label: "English", value: "en" }, { label: "Malayalam + English", value: "ml-en" },
  ] },
  { name: "lead_status", label: "Lead status", type: "select", required: true, options: ["NEW", "HOT", "WARM", "COLD", "FOLLOW_UP", "NOT_INTERESTED", "CONVERTED"].map((value) => ({ label: value.replaceAll("_", " "), value })) },
  { name: "consent_status", label: "Consent status", type: "select", required: true, options: ["UNKNOWN", "PENDING", "GRANTED", "DENIED"].map((value) => ({ label: value, value })) },
  { name: "calling_allowed", label: "Calling allowed", type: "checkbox", help: "Enable only when the company has permission to contact this client." },
  { name: "opted_out", label: "Opted out / Do not call", type: "checkbox", help: "Blocks future marketing calls in later phases." },
  { name: "notes", label: "Notes", type: "textarea", wide: true, placeholder: "Requirements, context, or internal notes" },
];

const leadTone = (status: string) => status === "HOT" ? "danger" : status === "WARM" || status === "FOLLOW_UP" ? "warning" : status === "CONVERTED" ? "success" : "info";

export default function ClientsPage() {
  return <ResourcePage
    title="Clients"
    singular="Client"
    endpoint="clients"
    description="Maintain consent-aware customer profiles and lead context for future conversations."
    fields={fields}
    initialValues={{ preferred_language: "ml", lead_status: "NEW", consent_status: "UNKNOWN", calling_allowed: false, opted_out: false }}
    columns={[
      { label: "Client", render: (record) => <div className="primary-cell"><strong>{String(record.name)}</strong><span>{truncate(record.business_name, 32)}</span></div> },
      { label: "Contact", render: (record) => <div className="primary-cell"><strong>{String(record.phone)}</strong><span>{truncate(record.email, 34)}</span></div> },
      { label: "Location", render: (record) => truncate(record.location, 28) },
      { label: "Lead", render: (record) => <StatusBadge tone={leadTone(String(record.lead_status))}>{String(record.lead_status).replaceAll("_", " ")}</StatusBadge> },
      { label: "Calling", render: (record) => record.opted_out ? <StatusBadge tone="danger">OPTED OUT</StatusBadge> : record.calling_allowed ? <StatusBadge tone="success">ALLOWED</StatusBadge> : <StatusBadge tone="neutral">NOT ENABLED</StatusBadge> },
      { label: "Added", render: (record) => formatDate(record.created_at) },
    ]}
  />;
}
