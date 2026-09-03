import PlatformModulePage from "@/components/platform-module-page";

export default function OfficeManagementPage() {
  return (
    <PlatformModulePage
      eyebrow="People and office operations"
      title="Office Management"
      description="Coordinate employees, attendance, leave, tasks, meetings, expenses, documents, and announcements from one company workspace."
      connectedWith={["Projects", "Accounting", "Company Assets", "Media Library", "Dashboard"]}
      areas={[
        { title: "Employees", description: "Maintain staff identity, role, department, contact, employment, and access details.", mark: "E" },
        { title: "Attendance", description: "Organize daily presence, work timing, late entry, and attendance corrections.", mark: "A" },
        { title: "Leave Management", description: "Handle leave requests, approval, balances, dates, and team availability.", mark: "L" },
        { title: "Tasks & Assignments", description: "Assign office or project work with owner, due date, priority, and status.", mark: "T" },
        { title: "Meetings & Calendar", description: "Coordinate internal meetings, client discussions, reminders, and schedules.", mark: "M" },
        { title: "Expenses & Reimbursements", description: "Submit, review, approve, and connect employee expenses to Accounting.", mark: "₹" },
        { title: "Office Documents", description: "Organize policies, letters, forms, employee files, and controlled documents.", mark: "D" },
        { title: "Announcements", description: "Publish company notices, office updates, events, and staff communication.", mark: "N" },
      ]}
    />
  );
}
