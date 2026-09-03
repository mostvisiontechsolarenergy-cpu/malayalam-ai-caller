import { cookies } from "next/headers";

export const ACCESS_COOKIE = "malayalam_ai_access";
export const COMPANY_COOKIE = "malayalam_ai_company";

export function backendBaseUrl() {
  return (
    process.env.INTERNAL_BACKEND_URL ??
    process.env.BACKEND_URL ??
    "http://localhost:8000"
  ).replace(/\/$/, "");
}

export async function authenticatedBackendFetch(
  path: string,
  init: RequestInit = {},
  includeCompany = true,
) {
  const cookieStore = await cookies();
  const accessToken = cookieStore.get(ACCESS_COOKIE)?.value;
  if (!accessToken) {
    return null;
  }

  const headers = new Headers(init.headers);
  headers.set("Authorization", `Bearer ${accessToken}`);
  if (includeCompany) {
    const companyId = cookieStore.get(COMPANY_COOKIE)?.value;
    if (companyId) headers.set("X-Company-ID", companyId);
  }

  return fetch(`${backendBaseUrl()}/api/v1/${path.replace(/^\//, "")}`, {
    ...init,
    headers,
    cache: "no-store",
  });
}

export const secureCookie = process.env.NODE_ENV === "production";
