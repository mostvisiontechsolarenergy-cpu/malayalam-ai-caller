"use client";

import ResourcePage, { StatusBadge, truncate, type FieldConfig } from "@/components/resource-page";

const fields: FieldConfig[] = [
  { name: "name", label: "Agent name", required: true, placeholder: "Malayalam Sales Assistant" },
  { name: "description", label: "Description", type: "textarea", wide: true, placeholder: "What this agent is designed to handle" },
  { name: "primary_language", label: "Primary language", type: "select", required: true, options: [{ label: "Malayalam", value: "ml" }, { label: "English", value: "en" }] },
  { name: "secondary_language", label: "Secondary language", type: "select", options: [{ label: "English", value: "en" }, { label: "Malayalam", value: "ml" }, { label: "None", value: "" }] },
  { name: "voice", label: "Assistant voice", type: "select", required: true, options: ["Kore", "Aoede", "Sulafat", "Puck", "Charon", "Leda", "Achird", "Zephyr", "marin", "cedar", "coral", "sage"].map((value) => ({ label: `${value[0].toUpperCase()}${value.slice(1)}`, value })), help: "Choose the voice used for customer conversations." },
  { name: "tone", label: "Tone", type: "select", required: true, options: ["Friendly Professional", "Warm Consultative", "Concise Support", "Formal Professional"].map((value) => ({ label: value, value })) },
  { name: "opening_message", label: "Opening message", type: "textarea", required: true, wide: true, placeholder: "Include clear AI disclosure and call purpose." },
  { name: "objective", label: "Conversation objective", type: "textarea", required: true, wide: true, placeholder: "Qualify interest and collect customer requirements." },
  { name: "system_prompt", label: "Agent instructions", type: "textarea", required: true, wide: true, placeholder: "Behavior boundaries, response style, and knowledge rules" },
  { name: "closing_instruction", label: "Closing instruction", type: "textarea", wide: true, placeholder: "Confirm next action and close politely." },
  { name: "active", label: "Active agent", type: "checkbox", help: "Available for selection when AI calling phases are connected." },
];

export default function AgentsPage() {
  return <ResourcePage
    title="AI Agents"
    singular="AI agent"
    endpoint="ai-agents"
    description="Design reusable Malayalam and English assistant profiles for future text, voice, and telephone conversations."
    note={<><strong>Shared agent profile:</strong> text tests, microphone tests, and telephone calls use these instructions, objectives, and voice settings.</>}
    fields={fields}
    initialValues={{ primary_language: "ml", secondary_language: "en", tone: "Friendly Professional", active: true, voice: "Kore" }}
    columns={[
      { label: "Agent", render: (record) => <div className="primary-cell"><strong>{String(record.name)}</strong><span>{truncate(record.description, 56)}</span></div> },
      { label: "Languages", render: (record) => `${String(record.primary_language).toUpperCase()}${record.secondary_language ? ` + ${String(record.secondary_language).toUpperCase()}` : ""}` },
      { label: "Tone", render: (record) => String(record.tone) },
      { label: "Objective", render: (record) => truncate(record.objective, 48) },
      { label: "Status", render: (record) => <StatusBadge tone={record.active ? "success" : "neutral"}>{record.active ? "ACTIVE" : "INACTIVE"}</StatusBadge> },
    ]}
  />;
}
