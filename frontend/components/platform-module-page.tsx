import Link from "next/link";

import { StatusBadge } from "@/components/resource-page";

export type ModuleArea = {
  title: string;
  description: string;
  mark: string;
  href?: string;
  status?: "Available" | "Foundation ready";
};

type PlatformModulePageProps = {
  eyebrow: string;
  title: string;
  description: string;
  areas: ModuleArea[];
  connectedWith: string[];
  primaryAction?: { href: string; label: string };
};

export default function PlatformModulePage({
  eyebrow,
  title,
  description,
  areas,
  connectedWith,
  primaryAction,
}: PlatformModulePageProps) {
  return (
    <>
      <div className="page-heading platform-module-heading">
        <div>
          <span className="eyebrow">{eyebrow}</span>
          <h1>{title}</h1>
          <p>{description}</p>
        </div>
        {primaryAction ? (
          <Link className="primary-button" href={primaryAction.href}>
            {primaryAction.label}
          </Link>
        ) : (
          <StatusBadge tone="info">MODULE FOUNDATION</StatusBadge>
        )}
      </div>

      <section className="module-area-grid">
        {areas.map((area) => {
          const content = (
            <>
              <div className="module-area-mark">{area.mark}</div>
              <div className="module-area-copy">
                <div>
                  <h2>{area.title}</h2>
                  <StatusBadge tone={area.href ? "success" : "neutral"}>
                    {area.status ?? (area.href ? "Available" : "Foundation ready")}
                  </StatusBadge>
                </div>
                <p>{area.description}</p>
              </div>
              {area.href ? <span className="module-area-arrow">→</span> : null}
            </>
          );
          return area.href ? (
            <Link className="module-area-card linked" href={area.href} key={area.title}>
              {content}
            </Link>
          ) : (
            <article className="module-area-card" key={area.title}>
              {content}
            </article>
          );
        })}
      </section>

      <section className="panel module-connections">
        <div>
          <span className="eyebrow">Shared company data</span>
          <h2>Connected across the platform</h2>
          <p>
            This workspace uses the same company and client context, so information can move
            between modules without duplicate entry as each workflow is activated.
          </p>
        </div>
        <div className="module-connection-list">
          {connectedWith.map((connection) => <span key={connection}>{connection}</span>)}
        </div>
      </section>
    </>
  );
}
