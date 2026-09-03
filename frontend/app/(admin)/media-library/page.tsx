import PlatformModulePage from "@/components/platform-module-page";

export default function MediaLibraryPage() {
  return (
    <PlatformModulePage
      eyebrow="Creative asset workspace"
      title="Media Library"
      description="Organize client and company images, videos, audio, designs, documents, versions, usage rights, and approvals."
      connectedWith={["Clients", "Projects", "Proposal Connect", "Maya AI", "Office Management"]}
      areas={[
        { title: "Client Media", description: "Separate every client's source files, brand assets, and approved deliverables.", mark: "C" },
        { title: "Project Files", description: "Connect working media and final output directly to project records.", mark: "P" },
        { title: "Images & Designs", description: "Organize artwork, posters, logos, brand files, and exported formats.", mark: "I" },
        { title: "Video & Audio", description: "Maintain footage, edits, advertisements, voice, and final media versions.", mark: "V" },
        { title: "Approvals & Versions", description: "Track review status, client feedback, current version, and final approval.", mark: "A" },
        { title: "Rights & Usage", description: "Record permitted channels, expiry, ownership, and reuse conditions.", mark: "R" },
      ]}
    />
  );
}
