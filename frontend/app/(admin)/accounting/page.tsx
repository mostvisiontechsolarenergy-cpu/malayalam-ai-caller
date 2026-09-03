import PlatformModulePage from "@/components/platform-module-page";

export default function AccountingPage() {
  return (
    <PlatformModulePage
      eyebrow="Financial operations"
      title="Accounting"
      description="Create a controlled company finance workspace connecting client revenue, project expenses, office costs, assets, and investments."
      connectedWith={["Clients", "Projects", "Proposal Connect", "Office Management", "Investments"]}
      areas={[
        { title: "Invoices & Receivables", description: "Track client invoices, due dates, receipts, balances, and overdue amounts.", mark: "I" },
        { title: "Income", description: "Classify project and non-project revenue with supporting records.", mark: "+" },
        { title: "Expenses", description: "Capture vendor, project, office, employee, and recurring operating expenses.", mark: "−" },
        { title: "Tax Records", description: "Organize applicable tax information and period-level documentation.", mark: "T" },
        { title: "Cash & Bank", description: "Maintain controlled cash, bank, transfer, and reconciliation records.", mark: "B" },
        { title: "Financial Reports", description: "Prepare profit, cash-flow, receivable, expense, and management summaries.", mark: "R" },
      ]}
    />
  );
}
