import PlatformModulePage from "@/components/platform-module-page";

export default function MayaAIPage() {
  return (
    <PlatformModulePage
      eyebrow="Intelligent operations"
      title="Maya AI"
      description="Manage Dcreation's customer-facing and internal assistants from one grounded intelligence workspace."
      primaryAction={{ href: "/phone-calls", label: "Open Calling Assistant" }}
      connectedWith={["Clients", "Sales Pipeline", "Proposal Connect", "Projects", "Knowledge Base"]}
      areas={[
        { title: "Calling Assistant", description: "Run consented Malayalam calls, sequential queues, callbacks, and call reports.", mark: "C", href: "/phone-calls" },
        { title: "AI Agents", description: "Configure Maya, Soorya, and future calling or non-calling assistants.", mark: "A", href: "/agents" },
        { title: "Knowledge Base", description: "Ground every assistant in approved company services, prices, offers, and policies.", mark: "K", href: "/knowledge" },
        { title: "Text Workspace", description: "Test grounded Malayalam conversations before using an assistant with customers.", mark: "T", href: "/ai-text-test" },
        { title: "Voice Playground", description: "Validate voice, opening messages, and conversation behaviour safely.", mark: "V", href: "/voice-playground" },
        { title: "Call Intelligence", description: "Review transcripts, customer requirements, questions, and next actions.", mark: "R", href: "/phone-calls" },
      ]}
    />
  );
}
