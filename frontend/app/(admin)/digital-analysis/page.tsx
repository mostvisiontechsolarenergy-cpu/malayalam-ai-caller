import PlatformModulePage from "@/components/platform-module-page";

export default function DigitalAnalysisPage() {
  return (
    <PlatformModulePage
      eyebrow="Business intelligence"
      title="Digital Analysis"
      description="A unified analysis workspace for client growth, campaigns, sales movement, project performance, and management decisions."
      connectedWith={["Clients", "Projects", "Sales Pipeline", "Accounting", "Maya AI"]}
      areas={[
        { title: "Client Growth", description: "Track enquiry sources, requirements, engagement, and conversion movement.", mark: "C" },
        { title: "Campaign Performance", description: "Bring channel, advertisement, reach, lead, and conversion analysis together.", mark: "M" },
        { title: "Sales Insights", description: "Measure pipeline value, stage movement, follow-ups, and conversion rates.", mark: "S" },
        { title: "Project Performance", description: "Compare delivery progress, timelines, workload, and profitability.", mark: "P" },
        { title: "Financial Overview", description: "Connect revenue, expense, receivable, and investment indicators.", mark: "F" },
        { title: "AI Insights", description: "Turn calls, client questions, and project activity into clear management signals.", mark: "A" },
      ]}
    />
  );
}
