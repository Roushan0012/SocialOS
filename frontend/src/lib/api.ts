/**
 * SocialOS API Client.
 * 
 * Centralized, typed HTTP client for backend REST endpoints.
 * Handles company isolation, error normalization, and authorization headers.
 * Security guarantee: Never parses or handles OAuth secrets or access tokens in frontend code.
 */

import {
  CompanyListResponse,
  OAuthStartResponse,
  Platform,
  SocialAccount,
  TokenRefreshResponse,
} from "@/types";

export class ApiError extends Error {
  status: number;
  detail: string;

  constructor(status: number, detail: string) {
    super(detail);
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
  }
}

const getApiBaseUrl = (): string => {
  if (process.env.NEXT_PUBLIC_API_URL) {
    return process.env.NEXT_PUBLIC_API_URL.replace(/\/+$/, "");
  }
  return "http://localhost:8000";
};

// Global memory token holder for authenticated sessions
let authToken: string | null = null;

export const setAuthToken = (token: string | null): void => {
  authToken = token;
};

export const getAuthToken = (): string | null => {
  if (authToken) return authToken;
  if (typeof window !== "undefined") {
    return localStorage.getItem("socialos_access_token");
  }
  return null;
};

async function apiRequest<T>(
  endpoint: string,
  options: RequestInit = {}
): Promise<T> {
  const baseUrl = getApiBaseUrl();
  const url = `${baseUrl}${endpoint.startsWith("/") ? endpoint : `/${endpoint}`}`;

  const headers: Record<string, string> = {
    Accept: "application/json",
    ...(options.headers as Record<string, string>),
  };

  if (options.body && typeof options.body === "string") {
    headers["Content-Type"] = "application/json";
  }

  const token = getAuthToken();
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  let response: Response;
  try {
    response = await fetch(url, {
      ...options,
      headers,
    });
  } catch (err: unknown) {
    const message = err instanceof Error ? err.message : "Network error";
    throw new ApiError(0, `Network error: ${message}`);
  }

  if (!response.ok) {
    let errorDetail = `Request failed with status ${response.status}`;
    try {
      const errorJson = await response.json();
      if (errorJson.detail) {
        if (typeof errorJson.detail === "string") {
          errorDetail = errorJson.detail;
        } else if (Array.isArray(errorJson.detail)) {
          errorDetail = errorJson.detail.map((d: { msg?: string }) => d.msg || "").join(", ");
        }
      }
    } catch {
      // Non-JSON response body fallback
    }
    throw new ApiError(response.status, errorDetail);
  }

  if (response.status === 204) {
    return {} as T;
  }

  return response.json();
}

/**
 * Company API methods
 */
export async function getCompanies(
  page: number = 1,
  pageSize: number = 50
): Promise<CompanyListResponse> {
  return apiRequest<CompanyListResponse>(
    `/api/v1/companies?page=${page}&page_size=${pageSize}`
  );
}

/**
 * Social Accounts & OAuth API methods
 */
export async function getSocialAccounts(
  companyId: string
): Promise<SocialAccount[]> {
  return apiRequest<SocialAccount[]>(
    `/api/v1/social/accounts?company_id=${encodeURIComponent(companyId)}`
  );
}

export async function startOAuthFlow(
  platform: Platform,
  companyId: string,
  redirectUri?: string
): Promise<OAuthStartResponse> {
  const query = new URLSearchParams({
    company_id: companyId,
  });
  if (redirectUri) {
    query.append("redirect_uri", redirectUri);
  }

  return apiRequest<OAuthStartResponse>(
    `/api/v1/social/oauth/${platform.toLowerCase()}/start?${query.toString()}`
  );
}

export async function disconnectSocialAccount(
  socialAccountId: string
): Promise<SocialAccount> {
  return apiRequest<SocialAccount>(
    `/api/v1/social/accounts/${encodeURIComponent(socialAccountId)}`,
    {
      method: "DELETE",
    }
  );
}

export async function refreshSocialAccount(
  socialAccountId: string
): Promise<TokenRefreshResponse> {
  return apiRequest<TokenRefreshResponse>(
    `/api/v1/social/accounts/${encodeURIComponent(socialAccountId)}/refresh`,
    {
      method: "POST",
    }
  );
}
