import PlatformModulePage from "@/components/platform-module-page";

export default function InvestmentsPage() {
  return (
    <PlatformModulePage
      eyebrow="Capital visibility"
      title="Investments"
      description="Track company capital allocation, investment records, ownership, documents, returns, and management decisions separately from operating expenses."
      connectedWith={["Accounting", "Company Assets", "Projects", "Documents", "Digital Analysis"]}
      areas={[
        { title: "Investment Register", description: "Record the category, amount, date, purpose, owner, and current status.", mark: "I" },
        { title: "Capital Allocation", description: "Show where company funds are committed across growth initiatives.", mark: "C" },
        { title: "Returns & Value", description: "Compare invested amount, realized return, current value, and expected outcome.", mark: "R" },
        { title: "Supporting Documents", description: "Maintain agreements, receipts, statements, approvals, and evidence.", mark: "D" },
        { title: "Review Schedule", description: "Plan recurring management reviews, maturity dates, and follow-up decisions.", mark: "S" },
        { title: "Analysis", description: "Connect investment movement with the management analysis workspace.", mark: "A" },
      ]}
    />
  );
}
