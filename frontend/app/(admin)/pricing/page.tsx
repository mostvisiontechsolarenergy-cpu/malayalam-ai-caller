"use client";

import ResourcePage, { StatusBadge, formatCurrency, formatDate, type FieldConfig, type LookupStore } from "@/components/resource-page";
import type { ApiRecord } from "@/lib/api";

const fields: FieldConfig[] = [
  { name: "product_id", label: "Product", type: "select", lookup: { endpoint: "products", labelKey: "name", placeholder: "Choose a product, or leave blank" } },
  { name: "service_id", label: "Service", type: "select", lookup: { endpoint: "services", labelKey: "name", placeholder: "Choose a service, or leave blank" } },
  { name: "package_name", label: "Package name", placeholder: "Starter, Pro, Enterprise…" },
  { name: "price", label: "Price", type: "number", required: true, min: 0, step: "0.01" },
  { name: "tier", label: "Price tier", type: "select", required: true, options: [
    { label: "Standard", value: "STANDARD" },
    { label: "MRP (quote first)", value: "MRP" },
    { label: "Normal (after discount request)", value: "NORMAL" },
    { label: "Least (internal final floor)", value: "LEAST" },
  ] },
  { name: "currency", label: "Currency", type: "select", required: true, options: [{ label: "Indian Rupee (INR)", value: "INR" }, { label: "US Dollar (USD)", value: "USD" }] },
  { name: "billing_type", label: "Billing type", type: "select", required: true, options: ["ONE_TIME", "MONTHLY", "YEARLY", "PER_UNIT", "CUSTOM"].map((value) => ({ label: value.replaceAll("_", " "), value })) },
  { name: "description", label: "Description", type: "textarea", wide: true, placeholder: "Package inclusions, exclusions, or pricing notes" },
  { name: "valid_from", label: "Valid from", type: "date" },
  { name: "valid_until", label: "Valid until", type: "date" },
  { name: "is_starting_price", label: "Starting price", type: "checkbox", help: "The amount is presented as a starting price." },
  { name: "tax_included", label: "Tax included", type: "checkbox" },
  { name: "active", label: "Active price", type: "checkbox", help: "Only active and currently valid prices are authoritative." },
];

function lookupName(record: ApiRecord, lookups: LookupStore) {
  const endpoint = record.product_id ? "products" : "services";
  const id = String(record.product_id ?? record.service_id ?? "");
  return String(lookups[endpoint]?.find((item) => item.id === id)?.name ?? "Unknown target");
}

export default function PricingPage() {
  return <ResourcePage
    title="Pricing"
    singular="Price"
    endpoint="prices"
    description="Maintain structured, time-bound prices. These records outrank unstructured knowledge."
    note={<><strong>Accuracy rule:</strong> select exactly one product or one service. The AI is never allowed to invent a missing price.</>}
    fields={fields}
    initialValues={{ currency: "INR", billing_type: "ONE_TIME", tier: "STANDARD", is_starting_price: false, tax_included: false, active: true }}
    validate={(payload) => Boolean(payload.product_id) === Boolean(payload.service_id) ? "Select exactly one product or one service." : payload.valid_from && payload.valid_until && String(payload.valid_until) < String(payload.valid_from) ? "Valid until cannot be earlier than valid from." : null}
    columns={[
      { label: "Target", render: (record, lookups) => <div className="primary-cell"><strong>{lookupName(record, lookups)}</strong><span>{String(record.package_name ?? (record.product_id ? "Product price" : "Service price"))}</span></div> },
      { label: "Price", render: (record) => <strong>{record.is_starting_price ? "From " : ""}{formatCurrency(record.price, String(record.currency))}</strong> },
      { label: "Tier", render: (record) => <StatusBadge tone={record.tier === "LEAST" ? "warning" : record.tier === "MRP" ? "info" : "neutral"}>{String(record.tier ?? "STANDARD")}</StatusBadge> },
      { label: "Billing", render: (record) => String(record.billing_type).replaceAll("_", " ") },
      { label: "Valid until", render: (record) => formatDate(record.valid_until) },
      { label: "Status", render: (record) => <StatusBadge tone={record.active ? "success" : "neutral"}>{record.active ? "ACTIVE" : "INACTIVE"}</StatusBadge> },
    ]}
  />;
}
