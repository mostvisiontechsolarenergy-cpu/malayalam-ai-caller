"use client";

import ResourcePage, { StatusBadge, truncate, type FieldConfig } from "@/components/resource-page";

const fields: FieldConfig[] = [
  { name: "name", label: "Product name", required: true, placeholder: "Product name" },
  { name: "category", label: "Category", placeholder: "Category" },
  { name: "short_description", label: "Short description", wide: true, placeholder: "One-line customer-friendly summary" },
  { name: "full_description", label: "Full description", type: "textarea", wide: true, placeholder: "Complete authoritative product description" },
  { name: "features", label: "Features", type: "tags", wide: true, placeholder: "Feature one, Feature two", help: "Separate items with commas." },
  { name: "benefits", label: "Benefits", type: "tags", wide: true, placeholder: "Benefit one, Benefit two", help: "Separate items with commas." },
  { name: "active", label: "Active product", type: "checkbox", help: "Only active products are available to AI retrieval." },
];

export default function ProductsPage() {
  return <ResourcePage title="Products" singular="Product" endpoint="products" description="Create the authoritative product catalog the AI will be allowed to use." fields={fields} initialValues={{ active: true, features: [], benefits: [] }} columns={[
    { label: "Product", render: (record) => <div className="primary-cell"><strong>{String(record.name)}</strong><span>{truncate(record.short_description, 54)}</span></div> },
    { label: "Category", render: (record) => truncate(record.category, 28) },
    { label: "Features", render: (record) => `${Array.isArray(record.features) ? record.features.length : 0} items` },
    { label: "Status", render: (record) => <StatusBadge tone={record.active ? "success" : "neutral"}>{record.active ? "ACTIVE" : "INACTIVE"}</StatusBadge> },
  ]} />;
}
