import { NextResponse } from "next/server";

import { backendBaseUrl } from "@/lib/server-api";

type RouteContext = { params: Promise<{ token: string }> };

export async function GET(_request: Request, context: RouteContext) {
  const { token } = await context.params;
  if (!/^[A-Za-z0-9_-]{32,64}$/.test(token)) {
    return NextResponse.json({ detail: "Invalid proposal link" }, { status: 404 });
  }

  const response = await fetch(
    `${backendBaseUrl()}/api/v1/proposals/shared/${encodeURIComponent(token)}/pdf`,
    { cache: "no-store" },
  );
  if (!response.ok) {
    return NextResponse.json(
      { detail: response.status === 404 ? "Shared proposal not found" : "Proposal unavailable" },
      { status: response.status },
    );
  }

  const headers = new Headers();
  headers.set("Content-Type", response.headers.get("content-type") ?? "application/pdf");
  headers.set("Cache-Control", "private, no-store");
  const disposition = response.headers.get("content-disposition");
  if (disposition) headers.set("Content-Disposition", disposition);
  return new NextResponse(await response.arrayBuffer(), { status: 200, headers });
}
