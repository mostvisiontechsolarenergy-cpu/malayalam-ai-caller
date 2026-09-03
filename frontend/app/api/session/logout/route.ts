import { NextResponse } from "next/server";

import { ACCESS_COOKIE, COMPANY_COOKIE, secureCookie } from "@/lib/server-api";

export async function POST() {
  const response = NextResponse.json({ authenticated: false });
  for (const name of [ACCESS_COOKIE, COMPANY_COOKIE]) {
    response.cookies.set(name, "", {
      httpOnly: true,
      sameSite: "lax",
      secure: secureCookie,
      path: "/",
      maxAge: 0,
    });
  }
  return response;
}
