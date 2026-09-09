/**
 * SocialOS Social Accounts & OAuth TypeScript Definitions.
 * 
 * Strict security invariant: No token or credential fields exist in these types.
 */

export type Platform = "INSTAGRAM" | "FACEBOOK" | "LINKEDIN" | "YOUTUBE";

export type SocialAccountStatus = "ACTIVE" | "DISCONNECTED" | "EXPIRED" | "ERROR";

export interface SocialAccount {
  id: string;
  company_id: string;
  platform: Platform;
  account_name: string;
  platform_account_id: string;
  status: SocialAccountStatus;
  token_expires_at: string | null;
  last_connected_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface OAuthStartResponse {
  authorization_url: string;
  state: string;
  platform: Platform;
}

export interface OAuthCallbackResponse {
  message: string;
  account: SocialAccount;
}

export interface TokenRefreshResponse {
  message: string;
  account: SocialAccount;
}

export interface SocialProviderInfo {
  platform: Platform;
  name: string;
  description: string;
  iconBg: string;
  iconColor: string;
  supportedFeatures: string[];
}
