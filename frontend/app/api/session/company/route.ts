import { NextRequest, NextResponse } from "next/server";

import {
  COMPANY_COOKIE,
  authenticatedBackendFetch,
  secureCookie,
} from "@/lib/server-api";

export async function POST(request: NextRequest) {
  const { companyId } = await request.json();
  const companiesResponse = await authenticatedBackendFetch("companies", {}, false);
  if (!companiesResponse) {
    return NextResponse.json({ detail: "Not authenticated" }, { status: 401 });
  }
  if (!companiesResponse.ok) {
    return NextResponse.json(await companiesResponse.json(), {
      status: companiesResponse.status,
    });
  }

  const companies = await companiesResponse.json();
  if (!companies.some((company: { id: string }) => company.id === companyId)) {
    return NextResponse.json({ detail: "Company access denied" }, { status: 403 });
  }

  const response = NextResponse.json({ selectedCompanyId: companyId });
  response.cookies.set(COMPANY_COOKIE, companyId, {
    httpOnly: true,
    sameSite: "lax",
    secure: secureCookie,
    path: "/",
    maxAge: 60 * 60 * 24 * 30,
  });
  return response;
}
