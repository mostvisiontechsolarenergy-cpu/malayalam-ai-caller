import PlatformModulePage from "@/components/platform-module-page";

export default function CompanyAssetsPage() {
  return (
    <PlatformModulePage
      eyebrow="Asset control"
      title="Company Assets"
      description="Maintain a reliable register of equipment, software, facilities, ownership, assignments, condition, and lifecycle events."
      connectedWith={["Office Management", "Projects", "Accounting", "Employees", "Media Library"]}
      areas={[
        { title: "Asset Register", description: "Record each physical, digital, and operational company asset.", mark: "A" },
        { title: "Employee Assignment", description: "Track custody, issue date, return, condition, and responsible employee.", mark: "E" },
        { title: "Maintenance", description: "Plan servicing, repairs, warranty, vendors, and maintenance costs.", mark: "M" },
        { title: "Licences & Subscriptions", description: "Control software licences, renewals, seats, subscriptions, and owners.", mark: "L" },
        { title: "Depreciation & Value", description: "Connect purchase value and lifecycle information with Accounting.", mark: "V" },
        { title: "Asset Documents", description: "Attach invoices, warranty cards, photographs, and related records.", mark: "D" },
      ]}
    />
  );
}
