"use client";

import { useRouter } from "next/navigation";
import { FormEvent, useEffect, useState } from "react";

import { apiRequest } from "@/lib/api";

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    apiRequest("session/me")
      .then(() => router.replace("/dashboard"))
      .catch(() => undefined);
  }, [router]);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setError("");
    setSubmitting(true);
    try {
      await apiRequest("session/login", {
        method: "POST",
        body: JSON.stringify({ email, password }),
      });
      setPassword("");
      router.replace("/dashboard");
      router.refresh();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Unable to sign in");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <main className="login-page">
      <section className="login-story">
        <div className="story-glow story-glow-one" />
        <div className="story-glow story-glow-two" />
        <div className="brand-lockup login-brand">
          <div className="brand-orb">M</div>
          <div>
            <strong>Dcreation Maya</strong>
            <span>Customer conversations, intelligently managed</span>
          </div>
        </div>
        <div className="story-content">
          <span className="eyebrow">Built for Kerala businesses</span>
          <h1>Your company knowledge, ready for every conversation.</h1>
          <p>
            Manage clients, catalog facts, current pricing, offers, FAQs, and Dcreation Maya
            assistants from one secure workspace.
          </p>
          <div className="story-points">
            <div><strong>Tenant-safe</strong><span>Company data stays isolated.</span></div>
            <div><strong>Authoritative</strong><span>Prices and offers come from real records.</span></div>
            <div><strong>Voice-ready</strong><span>Agent setup prepared for later calling phases.</span></div>
          </div>
        </div>
        <p className="story-footer">Phase 3 · Advanced Knowledge Workspace</p>
      </section>

      <section className="login-panel">
        <form className="login-card" onSubmit={submit}>
          <span className="eyebrow">Welcome back</span>
          <h2>Sign in to your workspace</h2>
          <p className="muted">Use the administrator account created during activation.</p>

          <label className="field-label">
            Email address
            <input
              type="email"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              autoComplete="email"
              placeholder="admin@company.com"
              required
            />
          </label>
          <label className="field-label">
            Password
            <input
              type="password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              autoComplete="current-password"
              placeholder="Enter your password"
              required
            />
          </label>
          {error ? <div className="form-error" role="alert">{error}</div> : null}
          <button className="primary-button login-button" disabled={submitting}>
            {submitting ? "Signing in…" : "Sign in securely"}
          </button>
          <div className="security-note">
            <span>●</span> Your access token is stored in a secure HTTP-only session cookie.
          </div>
        </form>
      </section>
    </main>
  );
}
