"use client";

import ResourcePage, { StatusBadge, formatCurrency, truncate, type FieldConfig } from "@/components/resource-page";

const fields: FieldConfig[] = [
  { name: "name", label: "Service name", required: true, placeholder: "Service name" },
  { name: "category", label: "Category", placeholder: "Category" },
  { name: "short_description", label: "Short description", wide: true, placeholder: "One-line customer-friendly summary" },
  { name: "full_description", label: "Full description", type: "textarea", wide: true },
  { name: "features", label: "Features", type: "tags", wide: true, placeholder: "Feature one, Feature two" },
  { name: "deliverables", label: "Deliverables", type: "tags", wide: true, placeholder: "Deliverable one, Deliverable two" },
  { name: "starting_price", label: "Starting price", type: "number", min: 0, step: "0.01", help: "A quick catalog reference; use Pricing for authoritative packages." },
  { name: "custom_quotation_required", label: "Custom quotation required", type: "checkbox" },
  { name: "active", label: "Active service", type: "checkbox", help: "Only active services are available to AI retrieval." },
];

export default function ServicesPage() {
  return <ResourcePage title="Services" singular="Service" endpoint="services" description="Define service capabilities, deliverables, and quotation requirements." fields={fields} initialValues={{ active: true, features: [], deliverables: [], custom_quotation_required: false }} columns={[
    { label: "Service", render: (record) => <div className="primary-cell"><strong>{String(record.name)}</strong><span>{truncate(record.short_description, 52)}</span></div> },
    { label: "Category", render: (record) => truncate(record.category, 28) },
    { label: "Starting from", render: (record) => record.starting_price == null ? "—" : formatCurrency(record.starting_price) },
    { label: "Quotation", render: (record) => record.custom_quotation_required ? <StatusBadge tone="warning">CUSTOM</StatusBadge> : <StatusBadge tone="info">STANDARD</StatusBadge> },
    { label: "Status", render: (record) => <StatusBadge tone={record.active ? "success" : "neutral"}>{record.active ? "ACTIVE" : "INACTIVE"}</StatusBadge> },
  ]} />;
}
