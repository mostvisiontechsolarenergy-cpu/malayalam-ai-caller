import PlatformModulePage from "@/components/platform-module-page";

export default function SalesPipelinePage() {
  return (
    <PlatformModulePage
      eyebrow="Revenue operations"
      title="Sales Pipeline"
      description="Move every permitted enquiry from qualification and follow-up through proposal, negotiation, conversion, or closure."
      primaryAction={{ href: "/clients", label: "Open Client CRM" }}
      connectedWith={["Clients", "Maya AI", "Proposal Connect", "Projects", "Accounting"]}
      areas={[
        { title: "New Enquiries", description: "Start from the existing client CRM and preserve source and contact permission.", mark: "N", href: "/clients" },
        { title: "Qualification", description: "Capture service need, budget expectation, urgency, and decision status.", mark: "Q" },
        { title: "Follow-ups", description: "Coordinate call outcomes, callback times, actions, and sales ownership.", mark: "F", href: "/phone-calls" },
        { title: "Proposal Stage", description: "Prepare the suitable service, approved price, terms, and proposal.", mark: "P", href: "/proposal-connect" },
        { title: "Negotiation", description: "Record objections, expected price, approved tiers, and agreed next steps.", mark: "N", href: "/pricing" },
        { title: "Conversion", description: "Convert accepted work into a project and financial record without re-entry.", mark: "C", href: "/projects" },
      ]}
    />
  );
}
