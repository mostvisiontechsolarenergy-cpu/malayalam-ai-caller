import { NextRequest, NextResponse } from "next/server";

import { ACCESS_COOKIE, backendBaseUrl, secureCookie } from "@/lib/server-api";

export async function POST(request: NextRequest) {
  const payload = await request.json();
  const response = await fetch(`${backendBaseUrl()}/api/v1/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
    cache: "no-store",
  });
  const data = await response.json();

  if (!response.ok) {
    return NextResponse.json(data, { status: response.status });
  }

  const result = NextResponse.json({ authenticated: true });
  result.cookies.set(ACCESS_COOKIE, data.access_token, {
    httpOnly: true,
    sameSite: "lax",
    secure: secureCookie,
    path: "/",
    maxAge: 60 * 60,
  });
  return result;
}
