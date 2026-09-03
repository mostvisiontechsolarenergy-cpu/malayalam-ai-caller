import PlatformModulePage from "@/components/platform-module-page";

export default function ProjectsPage() {
  return (
    <PlatformModulePage
      eyebrow="Delivery operations"
      title="Projects"
      description="Convert approved client work into controlled delivery plans with owners, tasks, milestones, files, and financial visibility."
      connectedWith={["Clients", "Proposal Connect", "Office Management", "Accounting", "Media Library"]}
      areas={[
        { title: "Project Workspace", description: "Maintain the client, scope, status, priority, and responsible project owner.", mark: "P" },
        { title: "Milestones", description: "Organize delivery stages, target dates, approvals, and completion status.", mark: "M" },
        { title: "Team Assignments", description: "Connect office employees, responsibilities, workload, and task ownership.", mark: "T" },
        { title: "Client Deliverables", description: "Track designs, campaigns, videos, documents, feedback, and approvals.", mark: "D" },
        { title: "Project Finance", description: "Connect quotation value, invoices, expenses, and project profitability.", mark: "F" },
        { title: "Project Files", description: "Use the Media Library as the controlled source for working and approved assets.", mark: "L" },
      ]}
    />
  );
}
