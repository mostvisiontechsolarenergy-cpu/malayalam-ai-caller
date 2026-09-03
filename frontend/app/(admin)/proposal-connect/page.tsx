"use client";

import Image from "next/image";
import { FormEvent, useEffect, useMemo, useRef, useState } from "react";

import { useSession } from "@/components/admin-shell";
import { formatCurrency, formatDate, StatusBadge } from "@/components/resource-page";
import { apiRequest } from "@/lib/api";

type Catalog = {
  id: string;
  name: string;
  short_description: string | null;
  active: boolean;
};
type Client = {
  id: string;
  name: string;
  business_name: string | null;
  phone: string;
  email: string | null;
  location: string | null;
};
type Price = {
  id: string;
  product_id: string | null;
  service_id: string | null;
  package_name: string | null;
  price: string | number;
  tier: string;
  currency: string;
  billing_type: string;
  description: string | null;
  active: boolean;
};
type Proposal = {
  id: string;
  client_id: string | null;
  client_name: string;
  client_business_name: string | null;
  client_phone: string | null;
  client_email: string | null;
  client_location: string | null;
  proposal_number: string;
  share_token: string;
  proposal_date: string;
  valid_until: string | null;
  project_start_date: string | null;
  project_end_date: string | null;
  status: string;
  currency: string;
  total_amount: string | number;
};
type LineItem = {
  id: string;
  kind: "CATALOG" | "CUSTOM";
  priceId: string;
  customName: string;
  description: string;
  customPrice: string;
  quantity: string;
};

function localDate(daysFromToday = 0) {
  const now = new Date();
  now.setDate(now.getDate() + daysFromToday);
  const offset = now.getTimezoneOffset() * 60_000;
  return new Date(now.valueOf() - offset).toISOString().slice(0, 10);
}

function emptyLine(id: string, kind: LineItem["kind"]): LineItem {
  return {
    id,
    kind,
    priceId: "",
    customName: "",
    description: "",
    customPrice: "",
    quantity: "1",
  };
}

export default function ProposalConnectPage() {
  const session = useSession();
  const canWrite = session.user.role !== "STAFF";
  const nextLine = useRef(2);
  const [services, setServices] = useState<Catalog[]>([]);
  const [products, setProducts] = useState<Catalog[]>([]);
  const [prices, setPrices] = useState<Price[]>([]);
  const [clients, setClients] = useState<Client[]>([]);
  const [proposals, setProposals] = useState<Proposal[]>([]);
  const [selectedClientId, setSelectedClientId] = useState("manual");
  const [clientName, setClientName] = useState("");
  const [clientBusinessName, setClientBusinessName] = useState("");
  const [clientPhone, setClientPhone] = useState("");
  const [clientEmail, setClientEmail] = useState("");
  const [clientLocation, setClientLocation] = useState("");
  const [proposalDate, setProposalDate] = useState(localDate);
  const [validUntil, setValidUntil] = useState(() => localDate(7));
  const [projectStartDate, setProjectStartDate] = useState(localDate);
  const [projectEndDate, setProjectEndDate] = useState("");
  const [notes, setNotes] = useState("");
  const [terms, setTerms] = useState("");
  const [lines, setLines] = useState<LineItem[]>([emptyLine("line-1", "CATALOG")]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [created, setCreated] = useState<Proposal | null>(null);
  const [copiedProposalId, setCopiedProposalId] = useState<string | null>(null);

  async function loadData() {
    setLoading(true);
    setError(null);
    try {
      const [serviceData, productData, priceData, clientData, proposalData] =
        await Promise.all([
          apiRequest<Catalog[]>("backend/services?limit=100"),
          apiRequest<Catalog[]>("backend/products?limit=100"),
          apiRequest<Price[]>("backend/prices?limit=100&current_only=true"),
          apiRequest<Client[]>("backend/clients?limit=100"),
          apiRequest<Proposal[]>("backend/proposals?limit=50"),
        ]);
      setServices(serviceData);
      setProducts(productData);
      setPrices(priceData.filter((price) => price.active && price.currency === "INR"));
      setClients(clientData);
      setProposals(proposalData);
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : "Could not load proposal data");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void loadData();
  }, []);

  const serviceMap = useMemo(
    () => new Map(services.map((service) => [service.id, service])),
    [services],
  );
  const productMap = useMemo(
    () => new Map(products.map((product) => [product.id, product])),
    [products],
  );
  const priceMap = useMemo(() => new Map(prices.map((price) => [price.id, price])), [prices]);

  function catalogName(price: Price) {
    const item = price.service_id
      ? serviceMap.get(price.service_id)
      : price.product_id
        ? productMap.get(price.product_id)
        : null;
    return item?.name ?? "Approved item";
  }

  function catalogLabel(price: Price) {
    const packageName = price.package_name ? ` - ${price.package_name}` : "";
    return `${catalogName(price)}${packageName} - ${price.tier} - ${formatCurrency(price.price, price.currency)}`;
  }

  function updateLine(id: string, values: Partial<LineItem>) {
    setLines((current) => current.map((line) => (line.id === id ? { ...line, ...values } : line)));
  }

  function addLine(kind: LineItem["kind"]) {
    const id = `line-${nextLine.current++}`;
    setLines((current) => [...current, emptyLine(id, kind)]);
  }

  function removeLine(id: string) {
    setLines((current) => current.filter((line) => line.id !== id));
  }

  function selectClient(clientId: string) {
    setSelectedClientId(clientId);
    if (clientId === "manual") {
      setClientName("");
      setClientBusinessName("");
      setClientPhone("");
      setClientEmail("");
      setClientLocation("");
      return;
    }
    const client = clients.find((item) => item.id === clientId);
    if (!client) return;
    setClientName(client.name);
    setClientBusinessName(client.business_name ?? "");
    setClientPhone(client.phone);
    setClientEmail(client.email ?? "");
    setClientLocation(client.location ?? "");
  }

  const total = useMemo(
    () =>
      lines.reduce((sum, line) => {
        const price = line.kind === "CATALOG"
          ? Number(priceMap.get(line.priceId)?.price ?? 0)
          : Number(line.customPrice || 0);
        return sum + price * Number(line.quantity || 0);
      }, 0),
    [lines, priceMap],
  );

  async function submit(event: FormEvent) {
    event.preventDefault();
    setError(null);
    setCreated(null);
    if (!clientName.trim()) {
      setError("Type the client name for this proposal.");
      return;
    }
    if (!lines.length) {
      setError("Add at least one proposal item.");
      return;
    }
    if (validUntil && validUntil < proposalDate) {
      setError("Valid-until date cannot be before the proposal date.");
      return;
    }
    if (projectStartDate && projectEndDate && projectEndDate < projectStartDate) {
      setError("Project end date cannot be before the project start date.");
      return;
    }
    const invalid = lines.find(
      (line) =>
        Number(line.quantity) <= 0 ||
        (line.kind === "CATALOG" && !line.priceId) ||
        (line.kind === "CUSTOM" && (!line.customName.trim() || line.customPrice === "")),
    );
    if (invalid) {
      setError("Complete the service/package, quantity, and price for every line.");
      return;
    }
    setSaving(true);
    try {
      const proposal = await apiRequest<Proposal>("backend/proposals", {
        method: "POST",
        body: JSON.stringify({
          client_id: selectedClientId === "manual" ? null : selectedClientId,
          client_name: clientName.trim(),
          client_business_name: clientBusinessName.trim() || null,
          client_phone: clientPhone.trim() || null,
          client_email: clientEmail.trim() || null,
          client_location: clientLocation.trim() || null,
          proposal_date: proposalDate,
          valid_until: validUntil || null,
          project_start_date: projectStartDate || null,
          project_end_date: projectEndDate || null,
          currency: "INR",
          notes: notes.trim() || null,
          terms: terms.trim() || null,
          items: lines.map((line) =>
            line.kind === "CATALOG"
              ? {
                  price_id: line.priceId,
                  description: line.description.trim() || null,
                  quantity: Number(line.quantity),
                }
              : {
                  custom_name: line.customName.trim(),
                  description: line.description.trim() || null,
                  custom_unit_price: Number(line.customPrice),
                  quantity: Number(line.quantity),
                },
          ),
        }),
      });
      setCreated(proposal);
      setProposals((current) => [proposal, ...current]);
      setLines([emptyLine(`line-${nextLine.current++}`, "CATALOG")]);
      setSelectedClientId("manual");
      setClientName("");
      setClientBusinessName("");
      setClientPhone("");
      setClientEmail("");
      setClientLocation("");
      setNotes("");
      setTerms("");
      setProposalDate(localDate());
      setValidUntil(localDate(7));
      setProjectStartDate(localDate());
      setProjectEndDate("");
    } catch (submitError) {
      setError(submitError instanceof Error ? submitError.message : "Could not create proposal");
    } finally {
      setSaving(false);
    }
  }

  async function copyShareLink(proposal: Proposal) {
    const shareUrl = `${window.location.origin}/api/shared-proposals/${proposal.share_token}`;
    try {
      await navigator.clipboard.writeText(shareUrl);
      setCopiedProposalId(proposal.id);
      window.setTimeout(() => setCopiedProposalId(null), 2500);
    } catch {
      window.prompt("Copy this proposal link", shareUrl);
    }
  }

  return (
    <>
      <header className="page-heading proposal-heading">
        <div>
          <span className="eyebrow">Proposal operations</span>
          <h1>Proposal Connect</h1>
          <p>Create a professional client proposal from approved knowledge packages, or add a custom service and price.</p>
        </div>
        <Image src="/dcreation-logo.png" alt="Dcreation" width={123} height={93} className="proposal-logo" priority />
      </header>

      {error ? <div className="form-error page-alert">{error}</div> : null}
      {created ? (
        <div className="proposal-success page-alert">
          <div>
            <strong>{created.proposal_number} is ready</strong>
            <span>The client-ready 10-page proposal brochure is ready to download or share.</span>
          </div>
          <div className="proposal-success-actions">
            <a className="primary-button" href={`/api/backend/proposals/${created.id}/pdf`}>
              Download 10-page proposal
            </a>
            <button className="secondary-button" type="button" onClick={() => copyShareLink(created)}>
              {copiedProposalId === created.id ? "Link copied" : "Copy share link"}
            </button>
          </div>
        </div>
      ) : null}

      <form className="proposal-form" onSubmit={submit}>
        <section className="panel proposal-card">
          <div className="proposal-card-heading">
            <div><span className="eyebrow">Proposal details</span><h2>Client and date</h2></div>
            <span className="proposal-step">01</span>
          </div>
          <div className="proposal-manual-client-grid">
            <label className="field-label proposal-client-source-field">
              Select existing client or enter a new client
              <select value={selectedClientId} onChange={(event) => selectClient(event.target.value)}>
                <option value="manual">+ Manual client (not in the client list)</option>
                {clients.map((client) => (
                  <option value={client.id} key={client.id}>
                    {client.business_name ? `${client.business_name} - ${client.name}` : client.name} - {client.phone}
                  </option>
                ))}
              </select>
            </label>
            <label className="field-label">
              Client name
              <input value={clientName} onChange={(event) => setClientName(event.target.value)} placeholder="Type client name" required />
            </label>
            <label className="field-label">
              Business or company (optional)
              <input value={clientBusinessName} onChange={(event) => setClientBusinessName(event.target.value)} placeholder="Business name" />
            </label>
            <label className="field-label">
              Phone (optional)
              <input type="tel" value={clientPhone} onChange={(event) => setClientPhone(event.target.value)} placeholder="Customer phone" />
            </label>
            <label className="field-label">
              Email (optional)
              <input type="email" value={clientEmail} onChange={(event) => setClientEmail(event.target.value)} placeholder="customer@example.com" />
            </label>
            <label className="field-label proposal-address-field">
              Address (optional)
              <input value={clientLocation} onChange={(event) => setClientLocation(event.target.value)} placeholder="Full client address" />
            </label>
            <label className="field-label">
              Proposal date
              <input type="date" value={proposalDate} onChange={(event) => setProposalDate(event.target.value)} required />
            </label>
            <label className="field-label">
              Valid until (optional)
              <input type="date" min={proposalDate} value={validUntil} onChange={(event) => setValidUntil(event.target.value)} />
            </label>
            <label className="field-label">
              Project start date (optional)
              <input type="date" value={projectStartDate} onChange={(event) => setProjectStartDate(event.target.value)} />
            </label>
            <label className="field-label">
              Project end date (optional)
              <input type="date" min={projectStartDate || proposalDate} value={projectEndDate} onChange={(event) => setProjectEndDate(event.target.value)} />
            </label>
          </div>
        </section>

        <section className="panel proposal-card">
          <div className="proposal-card-heading">
            <div><span className="eyebrow">Scope and value</span><h2>Services and packages</h2></div>
            <span className="proposal-step">02</span>
          </div>

          <div className="proposal-lines">
            {lines.map((line, index) => {
              const selectedPrice = priceMap.get(line.priceId);
              const unitPrice = line.kind === "CATALOG" ? Number(selectedPrice?.price ?? 0) : Number(line.customPrice || 0);
              const amount = unitPrice * Number(line.quantity || 0);
              return (
                <article className="proposal-line" key={line.id}>
                  <div className="proposal-line-number">{String(index + 1).padStart(2, "0")}</div>
                  <div className="proposal-line-body">
                    <div className="proposal-line-top">
                      <div className="proposal-kind-switch" aria-label={`Line ${index + 1} item type`}>
                        <button type="button" className={line.kind === "CATALOG" ? "active" : ""} onClick={() => updateLine(line.id, { kind: "CATALOG", customName: "", customPrice: "" })}>Knowledge package</button>
                        <button type="button" className={line.kind === "CUSTOM" ? "active" : ""} onClick={() => updateLine(line.id, { kind: "CUSTOM", priceId: "" })}>Custom service</button>
                      </div>
                      {lines.length > 1 ? <button type="button" className="proposal-remove" onClick={() => removeLine(line.id)}>Remove</button> : null}
                    </div>

                    {line.kind === "CATALOG" ? (
                      <div className="proposal-line-grid">
                        <label className="field-label proposal-package-field">
                          Approved package and price
                          <select value={line.priceId} onChange={(event) => updateLine(line.id, { priceId: event.target.value })} required>
                            <option value="">Choose from knowledge pricing</option>
                            {prices.map((price) => <option value={price.id} key={price.id}>{catalogLabel(price)}</option>)}
                          </select>
                        </label>
                        <label className="field-label">
                          Quantity
                          <input type="number" min="0.01" step="0.01" value={line.quantity} onChange={(event) => updateLine(line.id, { quantity: event.target.value })} required />
                        </label>
                        <div className="proposal-readonly-price"><span>Unit price</span><strong>{formatCurrency(unitPrice)}</strong></div>
                        <label className="field-label proposal-description-field">
                          Scope override (optional)
                          <input value={line.description} onChange={(event) => updateLine(line.id, { description: event.target.value })} placeholder="Leave blank to use the approved knowledge description and features" />
                        </label>
                      </div>
                    ) : (
                      <div className="proposal-line-grid proposal-custom-grid">
                        <label className="field-label">
                          Custom service
                          <input value={line.customName} onChange={(event) => updateLine(line.id, { customName: event.target.value })} placeholder="Example: Campaign strategy" required />
                        </label>
                        <label className="field-label">
                          Custom price
                          <input type="number" min="0" step="0.01" value={line.customPrice} onChange={(event) => updateLine(line.id, { customPrice: event.target.value })} placeholder="0.00" required />
                        </label>
                        <label className="field-label">
                          Quantity
                          <input type="number" min="0.01" step="0.01" value={line.quantity} onChange={(event) => updateLine(line.id, { quantity: event.target.value })} required />
                        </label>
                        <label className="field-label proposal-description-field">
                          Description (optional - blank by default)
                          <input value={line.description} onChange={(event) => updateLine(line.id, { description: event.target.value })} placeholder="Type only when a description is needed" />
                        </label>
                      </div>
                    )}
                    <div className="proposal-line-summary">
                      <span>{selectedPrice ? `${catalogName(selectedPrice)} - ${selectedPrice.billing_type.replaceAll("_", " ")}` : line.customName || "Complete this item to calculate the amount."}</span>
                      <strong>{formatCurrency(amount)}</strong>
                    </div>
                  </div>
                </article>
              );
            })}
          </div>

          <div className="proposal-add-actions">
            <button type="button" className="secondary-button" onClick={() => addLine("CATALOG")}>+ Approved package</button>
            <button type="button" className="secondary-button" onClick={() => addLine("CUSTOM")}>+ Custom service</button>
          </div>
        </section>

        <section className="panel proposal-card proposal-final-card">
          <div>
            <div className="proposal-card-heading">
              <div><span className="eyebrow">Final details</span><h2>Notes and terms</h2></div>
              <span className="proposal-step">03</span>
            </div>
            <div className="proposal-text-grid">
              <label className="field-label">Notes<textarea rows={4} value={notes} onChange={(event) => setNotes(event.target.value)} placeholder="Project notes or special inclusions" /></label>
              <label className="field-label">Terms<textarea rows={4} value={terms} onChange={(event) => setTerms(event.target.value)} placeholder="Payment, delivery, or validity terms" /></label>
            </div>
          </div>
          <aside className="proposal-total-card">
            <span>Proposal total</span>
            <strong>{formatCurrency(total)}</strong>
            <small>{lines.length} {lines.length === 1 ? "line item" : "line items"} - INR</small>
            <button className="primary-button" type="submit" disabled={!canWrite || saving || loading}>
              {saving ? "Creating PDF..." : canWrite ? "Create proposal" : "Admin access required"}
            </button>
          </aside>
        </section>
      </form>

      <section className="data-card proposal-history">
        <div className="table-toolbar"><div><strong>Proposal history</strong><span>{proposals.length} saved proposals</span></div></div>
        <div className="table-scroll">
          <table className="data-table">
            <thead><tr><th>Proposal</th><th>Client</th><th>Proposal date</th><th>Project dates</th><th>Total</th><th>Status</th><th className="actions-column">Download / share</th></tr></thead>
            <tbody>
              {proposals.length ? proposals.map((proposal) => (
                <tr key={proposal.id}>
                  <td className="primary-cell"><strong>{proposal.proposal_number}</strong><span>Valid until {formatDate(proposal.valid_until)}</span></td>
                  <td>{proposal.client_name}</td>
                  <td>{formatDate(proposal.proposal_date)}</td>
                  <td>{proposal.project_start_date ? `${formatDate(proposal.project_start_date)} - ${formatDate(proposal.project_end_date)}` : "Not scheduled"}</td>
                  <td><strong>{formatCurrency(proposal.total_amount, proposal.currency)}</strong></td>
                  <td><StatusBadge tone={proposal.status === "ACCEPTED" ? "success" : "info"}>{proposal.status}</StatusBadge></td>
                  <td className="row-actions proposal-row-actions">
                    <a href={`/api/backend/proposals/${proposal.id}/pdf`}>Download</a>
                    <button type="button" onClick={() => copyShareLink(proposal)}>
                      {copiedProposalId === proposal.id ? "Copied" : "Share link"}
                    </button>
                  </td>
                </tr>
              )) : <tr><td colSpan={7} className="proposal-empty">No proposals yet. Create the first one above.</td></tr>}
            </tbody>
          </table>
        </div>
      </section>
    </>
  );
}
