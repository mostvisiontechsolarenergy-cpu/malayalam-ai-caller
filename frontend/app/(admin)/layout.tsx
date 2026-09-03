import AdminShell from "@/components/admin-shell";

export default function ProtectedLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <AdminShell>{children}</AdminShell>;
}
