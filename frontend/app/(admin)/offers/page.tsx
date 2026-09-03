"use client";

import ResourcePage, { StatusBadge, formatCurrency, formatDate, truncate, type FieldConfig, type LookupStore } from "@/components/resource-page";
import type { ApiRecord } from "@/lib/api";

const fields: FieldConfig[] = [
  { name: "title", label: "Offer title", required: true, placeholder: "Onam Offer" },
  { name: "product_id", label: "Product", type: "select", lookup: { endpoint: "products", labelKey: "name", placeholder: "Optional product" } },
  { name: "service_id", label: "Service", type: "select", lookup: { endpoint: "services", labelKey: "name", placeholder: "Optional service" } },
  { name: "description", label: "Description", type: "textarea", wide: true },
  { name: "original_price", label: "Original price", type: "number", min: 0, step: "0.01" },
  { name: "offer_price", label: "Offer price", type: "number", min: 0, step: "0.01" },
  { name: "discount_type", label: "Discount type", type: "select", required: true, options: ["NONE", "FIXED", "PERCENTAGE"].map((value) => ({ label: value, value })) },
  { name: "discount_value", label: "Discount value", type: "number", min: 0, step: "0.01" },
  { name: "valid_from", label: "Valid from", type: "date" },
  { name: "valid_until", label: "Valid until", type: "date" },
  { name: "terms", label: "Terms", type: "textarea", wide: true, placeholder: "Eligibility, exclusions, and conditions" },
  { name: "active", label: "Offer enabled", type: "checkbox", help: "Expired offers are automatically excluded even when enabled." },
];

function targetName(record: ApiRecord, lookups: LookupStore) {
  if (!record.product_id && !record.service_id) return "Company-wide";
  const endpoint = record.product_id ? "products" : "services";
  const id = String(record.product_id ?? record.service_id);
  return String(lookups[endpoint]?.find((item) => item.id === id)?.name ?? "Unavailable target");
}

const statusTone = (status: string) => status === "ACTIVE" ? "success" : status === "UPCOMING" ? "info" : status === "EXPIRED" ? "danger" : "neutral";

export default function OffersPage() {
  return <ResourcePage
    title="Offers"
    singular="Offer"
    endpoint="offers"
    description="Publish controlled promotions with explicit validity and terms."
    note={<><strong>Automatic validity:</strong> expired and disabled offers remain visible to admins but are never returned as current AI knowledge.</>}
    fields={fields}
    initialValues={{ discount_type: "NONE", active: true }}
    validate={(payload) => payload.product_id && payload.service_id ? "An offer can target a product or a service, not both." : payload.valid_from && payload.valid_until && String(payload.valid_until) < String(payload.valid_from) ? "Valid until cannot be earlier than valid from." : null}
    columns={[
      { label: "Offer", render: (record) => <div className="primary-cell"><strong>{String(record.title)}</strong><span>{truncate(record.description, 52)}</span></div> },
      { label: "Target", render: targetName },
      { label: "Offer price", render: (record) => record.offer_price == null ? "—" : formatCurrency(record.offer_price) },
      { label: "Valid until", render: (record) => formatDate(record.valid_until) },
      { label: "Status", render: (record) => <StatusBadge tone={statusTone(String(record.status))}>{String(record.status)}</StatusBadge> },
    ]}
  />;
}
