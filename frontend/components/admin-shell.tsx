"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import {
  createContext,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";

import { apiRequest } from "@/lib/api";

type Company = { id: string; name: string };
type User = {
  id: string;
  company_id: string | null;
  name: string;
  email: string;
  role: "SUPER_ADMIN" | "ADMIN" | "STAFF";
};
type Session = { user: User; companies: Company[]; selectedCompanyId: string | null };

const SessionContext = createContext<Session | null>(null);

export function useSession() {
  const session = useContext(SessionContext);
  if (!session) throw new Error("Session is unavailable");
  return session;
}

const navigationGroups = [
  {
    label: "Platform",
    items: [
      { href: "/dashboard", label: "Dashboard", mark: "D" },
      { href: "/digital-analysis", label: "Digital Analysis", mark: "A" },
      { href: "/clients", label: "Clients", mark: "C" },
      { href: "/projects", label: "Projects", mark: "P" },
      { href: "/sales-pipeline", label: "Sales Pipeline", mark: "S" },
    ],
  },
  {
    label: "Maya AI",
    items: [
      { href: "/maya-ai", label: "Maya AI Home", mark: "M" },
      { href: "/phone-calls", label: "Calling Assistant", mark: "C" },
      { href: "/call-reports", label: "Call Reports", mark: "R" },
      { href: "/agents", label: "AI Agents", mark: "A" },
      { href: "/knowledge", label: "Knowledge Base", mark: "K" },
      { href: "/voice-playground", label: "Voice Playground", mark: "V" },
      { href: "/ai-text-test", label: "Text Workspace", mark: "T" },
    ],
  },
  {
    label: "Business Operations",
    items: [
      { href: "/proposal-connect", label: "Proposal Connect", mark: "P" },
      { href: "/accounting", label: "Accounting", mark: "A" },
      { href: "/office-management", label: "Office Management", mark: "O" },
      { href: "/company-assets", label: "Company Assets", mark: "C" },
      { href: "/investments", label: "Investments", mark: "I" },
      { href: "/media-library", label: "Media Library", mark: "L" },
    ],
  },
  {
    label: "Company Knowledge",
    items: [
      { href: "/documents", label: "Documents", mark: "D" },
      { href: "/knowledge-health", label: "Knowledge Health", mark: "H" },
      { href: "/knowledge-test", label: "Knowledge Test", mark: "T" },
      { href: "/products", label: "Products", mark: "P" },
      { href: "/services", label: "Services", mark: "S" },
      { href: "/pricing", label: "Pricing", mark: "Rs" },
      { href: "/offers", label: "Offers", mark: "%" },
      { href: "/faqs", label: "FAQs", mark: "?" },
    ],
  },
];

export default function AdminShell({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const [session, setSession] = useState<Session | null>(null);
  const [loading, setLoading] = useState(true);
  const [mobileOpen, setMobileOpen] = useState(false);

  useEffect(() => {
    let active = true;
    apiRequest<Session>("session/me")
      .then((data) => {
        if (active) setSession(data);
      })
      .catch(() => router.replace("/login"))
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [router]);

  const currentCompany = useMemo(
    () => session?.companies.find((company) => company.id === session.selectedCompanyId),
    [session],
  );

  async function switchCompany(companyId: string) {
    await apiRequest("session/company", {
      method: "POST",
      body: JSON.stringify({ companyId }),
    });
    window.location.reload();
  }

  async function logout() {
    await apiRequest("session/logout", { method: "POST" });
    router.replace("/login");
    router.refresh();
  }

  if (loading || !session) {
    return (
      <main className="app-loader" aria-live="polite">
        <div className="brand-orb">D</div>
        <div className="loading-line" />
        <p>Opening your workspace…</p>
      </main>
    );
  }

  const initials = session.user.name
    .split(" ")
    .map((part) => part[0])
    .join("")
    .slice(0, 2)
    .toUpperCase();

  return (
    <SessionContext.Provider value={session}>
      <div className="admin-layout">
        <button
          className={`sidebar-scrim ${mobileOpen ? "visible" : ""}`}
          aria-label="Close navigation"
          onClick={() => setMobileOpen(false)}
        />
        <aside className={`sidebar ${mobileOpen ? "open" : ""}`}>
          <div className="brand-lockup">
            <div className="brand-orb">D</div>
            <div>
              <strong>Dcreation Platform</strong>
              <span>Digitalization workspace</span>
            </div>
          </div>

          <nav aria-label="Main navigation">
            {navigationGroups.map((group, groupIndex) => (
              <div className="nav-group" key={group.label}>
                <p className={`nav-label ${groupIndex ? "nav-label-spaced" : ""}`}>
                  {group.label}
                </p>
                {group.items.map((item) => {
                  const selected = pathname === item.href || pathname.startsWith(`${item.href}/`);
                  return (
                    <Link
                      href={item.href}
                      key={item.href}
                      className={`nav-item ${selected ? "active" : ""}`}
                      onClick={() => setMobileOpen(false)}
                    >
                      <span className="nav-mark">{item.mark}</span>
                      {item.label}
                    </Link>
                  );
                })}
              </div>
            ))}
          </nav>

          <div className="sidebar-profile">
            <div className="avatar">{initials}</div>
            <div className="profile-copy">
              <strong>{session.user.name}</strong>
              <span>{session.user.role.replace("_", " ")}</span>
            </div>
            <button className="icon-button" onClick={logout} aria-label="Sign out" title="Sign out">
              ↗
            </button>
          </div>
        </aside>

        <div className="workspace">
          <header className="topbar">
            <button
              className="mobile-menu"
              onClick={() => setMobileOpen(true)}
              aria-label="Open navigation"
            >
              ☰
            </button>
            <div className="company-context">
              <span>Company workspace</span>
              {session.companies.length > 1 ? (
                <select
                  aria-label="Select company"
                  value={session.selectedCompanyId ?? ""}
                  onChange={(event) => switchCompany(event.target.value)}
                >
                  {session.companies.map((company) => (
                    <option value={company.id} key={company.id}>
                      {company.name}
                    </option>
                  ))}
                </select>
              ) : (
                <strong>{currentCompany?.name ?? "Company"}</strong>
              )}
            </div>
            <div className="topbar-status">
              <span className="live-dot" />
              Systems online
            </div>
            {session.user.role !== "STAFF" ? (
              <Link className="topbar-proposal-link" href="/proposal-connect">
                + Create Proposal
              </Link>
            ) : null}
          </header>
          <main className="page-content">{children}</main>
        </div>
      </div>
    </SessionContext.Provider>
  );
}
