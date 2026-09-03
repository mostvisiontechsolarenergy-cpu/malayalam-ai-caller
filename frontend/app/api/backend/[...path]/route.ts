import { NextRequest, NextResponse } from "next/server";

import { authenticatedBackendFetch } from "@/lib/server-api";

type RouteContext = { params: Promise<{ path: string[] }> };

async function proxy(request: NextRequest, context: RouteContext) {
  const { path } = await context.params;
  const resourcePath = path.join("/");
  const allowedRoot = new Set([
    "dashboard",
    "clients",
    "products",
    "services",
    "prices",
    "offers",
    "proposals",
    "faqs",
    "knowledge-items",
    "knowledge",
    "documents",
    "ai-agents",
    "ai",
    "telephony",
    "reports",
  ]);
  if (!allowedRoot.has(path[0])) {
    return NextResponse.json({ detail: "Unsupported resource" }, { status: 404 });
  }

  const body = ["GET", "HEAD"].includes(request.method) ? undefined : await request.arrayBuffer();
  const response = await authenticatedBackendFetch(
    `${resourcePath}${request.nextUrl.search}`,
    {
      method: request.method,
      headers: body ? { "Content-Type": request.headers.get("content-type") ?? "application/json" } : {},
      body,
    },
  );
  if (!response) {
    return NextResponse.json({ detail: "Not authenticated" }, { status: 401 });
  }

  const responseBody = response.status === 204 ? null : await response.arrayBuffer();
  const headers = new Headers();
  const contentType = response.headers.get("content-type");
  const contentDisposition = response.headers.get("content-disposition");
  if (contentType) headers.set("Content-Type", contentType);
  if (contentDisposition) headers.set("Content-Disposition", contentDisposition);
  return new NextResponse(responseBody, {
    status: response.status,
    headers,
  });
}

export const GET = proxy;
export const POST = proxy;
export const PATCH = proxy;
export const DELETE = proxy;
