"use client";

import ResourcePage, { StatusBadge, truncate, type FieldConfig } from "@/components/resource-page";

const fields: FieldConfig[] = [
  { name: "question", label: "Question", type: "textarea", required: true, wide: true, placeholder: "A customer question in Malayalam, English, or both" },
  { name: "answer", label: "Approved answer", type: "textarea", required: true, wide: true, placeholder: "The authoritative response" },
  { name: "category", label: "Category", placeholder: "Sales, support, delivery…" },
  { name: "language", label: "Language", type: "select", required: true, options: [{ label: "Malayalam", value: "ml" }, { label: "English", value: "en" }, { label: "Malayalam + English", value: "ml-en" }] },
  { name: "keywords", label: "Keywords", type: "tags", wide: true, placeholder: "website, price, rate", help: "Separate matching terms with commas." },
  { name: "priority", label: "Priority", type: "number", required: true, min: 0, max: 100 },
  { name: "active", label: "Active FAQ", type: "checkbox", help: "Only active FAQs are considered for retrieval." },
];

export default function FAQsPage() {
  return <ResourcePage title="FAQs" singular="FAQ" endpoint="faqs" description="Create approved answers for common Malayalam and English customer questions." fields={fields} initialValues={{ language: "ml", priority: 0, active: true, keywords: [] }} columns={[
    { label: "Question", render: (record) => <div className="primary-cell"><strong>{truncate(record.question, 72)}</strong><span>{truncate(record.answer, 78)}</span></div> },
    { label: "Category", render: (record) => truncate(record.category, 24) },
    { label: "Language", render: (record) => String(record.language).toUpperCase() },
    { label: "Priority", render: (record) => String(record.priority) },
    { label: "Status", render: (record) => <StatusBadge tone={record.active ? "success" : "neutral"}>{record.active ? "ACTIVE" : "INACTIVE"}</StatusBadge> },
  ]} />;
}
