import { NextResponse } from "next/server";
import { cookies } from "next/headers";

import {
  COMPANY_COOKIE,
  authenticatedBackendFetch,
  secureCookie,
} from "@/lib/server-api";

export async function GET() {
  const userResponse = await authenticatedBackendFetch("auth/me", {}, false);
  if (!userResponse) {
    return NextResponse.json({ detail: "Not authenticated" }, { status: 401 });
  }
  if (!userResponse.ok) {
    return NextResponse.json(
      await userResponse.json(),
      { status: userResponse.status },
    );
  }

  const companiesResponse = await authenticatedBackendFetch("companies", {}, false);
  if (!companiesResponse?.ok) {
    return NextResponse.json(
      { detail: "Unable to load company access" },
      { status: companiesResponse?.status ?? 502 },
    );
  }

  const user = await userResponse.json();
  const companies = await companiesResponse.json();
  const cookieStore = await cookies();
  const requestedCompany = cookieStore.get(COMPANY_COOKIE)?.value;
  const allowed = companies.some((company: { id: string }) => company.id === requestedCompany);
  const selectedCompanyId = allowed
    ? requestedCompany
    : user.company_id ?? companies[0]?.id ?? null;

  const response = NextResponse.json({ user, companies, selectedCompanyId });
  if (selectedCompanyId && selectedCompanyId !== requestedCompany) {
    response.cookies.set(COMPANY_COOKIE, selectedCompanyId, {
      httpOnly: true,
      sameSite: "lax",
      secure: secureCookie,
      path: "/",
      maxAge: 60 * 60 * 24 * 30,
    });
  }
  return response;
}
