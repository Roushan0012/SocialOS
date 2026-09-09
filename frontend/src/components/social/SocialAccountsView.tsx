"use client";

import React, { useCallback, useEffect, useState } from "react";
import { Company, Platform, SocialAccount } from "@/types";
import {
  disconnectSocialAccount,
  getCompanies,
  getSocialAccounts,
  refreshSocialAccount,
  startOAuthFlow,
} from "@/lib/api";
import { AccountEmptyState } from "./AccountEmptyState";
import { AccountErrorState } from "./AccountErrorState";
import { AccountSkeleton } from "./AccountSkeleton";
import { CompanySelector } from "./CompanySelector";
import { ConnectAccountDialog } from "./ConnectAccountDialog";
import { DisconnectAccountDialog } from "./DisconnectAccountDialog";
import { OAuthToastBanner, ToastMessage } from "./OAuthToastBanner";
import { PROVIDERS_LIST, ProviderCard } from "./ProviderCard";
import { SocialAccountCard } from "./SocialAccountCard";

interface SocialAccountsViewProps {
  initialCompanies?: Company[];
  initialSelectedCompanyId?: string;
}

export const SocialAccountsView: React.FC<SocialAccountsViewProps> = ({
  initialCompanies = [],
  initialSelectedCompanyId,
}) => {
  // Company state
  const [companies, setCompanies] = useState<Company[]>(initialCompanies);
  const [selectedCompanyId, setSelectedCompanyId] = useState<string | null>(
    initialSelectedCompanyId || (initialCompanies.length > 0 ? initialCompanies[0].id : null)
  );
  const [isLoadingCompanies, setIsLoadingCompanies] = useState<boolean>(initialCompanies.length === 0);

  // Accounts state
  const [accounts, setAccounts] = useState<SocialAccount[]>([]);
  const [isLoadingAccounts, setIsLoadingAccounts] = useState<boolean>(true);
  const [accountsError, setAccountsError] = useState<string | null>(null);

  // Active view tab: 'accounts' | 'providers'
  const [activeTab, setActiveTab] = useState<"accounts" | "providers">("accounts");
  const [platformFilter, setPlatformFilter] = useState<string>("ALL");

  // Interaction states
  const [isConnectDialogOpen, setIsConnectDialogOpen] = useState<boolean>(false);
  const [connectingPlatform, setConnectingPlatform] = useState<Platform | null>(null);
  const [disconnectTarget, setDisconnectTarget] = useState<SocialAccount | null>(null);
  const [isDisconnecting, setIsDisconnecting] = useState<boolean>(false);
  const [refreshingAccountId, setRefreshingAccountId] = useState<string | null>(null);

  // Notifications
  const [toast, setToast] = useState<ToastMessage | null>(null);

  // 1. Fetch companies if not provided
  useEffect(() => {
    let isMounted = true;
    async function loadCompanies() {
      if (initialCompanies.length > 0) return;
      try {
        setIsLoadingCompanies(true);
        const res = await getCompanies();
        if (isMounted && res.items.length > 0) {
          setCompanies(res.items);
          setSelectedCompanyId((prev) => prev || res.items[0].id);
        }
      } catch (err: unknown) {
        if (isMounted) {
          const msg = err instanceof Error ? err.message : "Failed to load brands";
          setToast({
            id: "load-companies-err",
            type: "error",
            title: "Could not load brand workspaces",
            description: msg,
          });
        }
      } finally {
        if (isMounted) setIsLoadingCompanies(false);
      }
    }

    loadCompanies();
    return () => {
      isMounted = false;
    };
  }, [initialCompanies]);

  // 2. Fetch social accounts whenever selected company changes
  const loadAccounts = useCallback(async (companyId: string) => {
    setIsLoadingAccounts(true);
    setAccountsError(null);
    try {
      const data = await getSocialAccounts(companyId);
      setAccounts(data);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to load social accounts";
      setAccountsError(msg);
      setAccounts([]);
    } finally {
      setIsLoadingAccounts(false);
    }
  }, []);

  useEffect(() => {
    if (selectedCompanyId) {
      loadAccounts(selectedCompanyId);
    } else {
      setIsLoadingAccounts(false);
      setAccounts([]);
    }
  }, [selectedCompanyId, loadAccounts]);

  // 3. Inspect and handle OAuth URL callbacks
  useEffect(() => {
    if (typeof window === "undefined") return;

    const params = new URLSearchParams(window.location.search);
    const oauthStatus = params.get("oauth");
    const platformParam = params.get("platform");
    const errorMsg = params.get("error_description") || params.get("error");

    if (oauthStatus === "success") {
      setToast({
        id: "oauth-success",
        type: "success",
        title: "Account connected successfully",
        description: platformParam
          ? `Your ${platformParam.toUpperCase()} channel is now connected and ready.`
          : "Your social channel is now connected.",
      });
      // Clean query params from URL without page reload
      window.history.replaceState({}, document.title, window.location.pathname);
    } else if (oauthStatus === "error" || errorMsg) {
      setToast({
        id: "oauth-error",
        type: "error",
        title: "Account connection failed",
        description: errorMsg ? decodeURIComponent(errorMsg) : "Please try connecting the account again.",
      });
      window.history.replaceState({}, document.title, window.location.pathname);
    }
  }, []);

  // 4. Connect flow
  const handleConnectStart = async (platform: Platform) => {
    if (!selectedCompanyId) {
      setToast({
        id: "no-company",
        type: "error",
        title: "No brand selected",
        description: "Please select a brand workspace before connecting a social account.",
      });
      return;
    }

    try {
      setConnectingPlatform(platform);
      const res = await startOAuthFlow(platform, selectedCompanyId);
      if (res.authorization_url) {
        // External redirect
        window.location.href = res.authorization_url;
      } else {
        throw new Error("Missing authorization redirect URL from server");
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to initiate connection";
      setToast({
        id: "connect-err",
        type: "error",
        title: `Could not connect ${platform}`,
        description: msg,
      });
      setConnectingPlatform(null);
    }
  };

  // 5. Disconnect flow
  const handleConfirmDisconnect = async () => {
    if (!disconnectTarget) return;

    try {
      setIsDisconnecting(true);
      await disconnectSocialAccount(disconnectTarget.id);

      setToast({
        id: "disconnect-success",
        type: "success",
        title: "Account disconnected",
        description: `@${disconnectTarget.account_name} was removed from this brand.`,
      });

      // Reload accounts for the company
      if (selectedCompanyId) {
        await loadAccounts(selectedCompanyId);
      }
      setDisconnectTarget(null);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Disconnect request failed";
      setToast({
        id: "disconnect-err",
        type: "error",
        title: "Could not disconnect account",
        description: msg,
      });
    } finally {
      setIsDisconnecting(false);
    }
  };

  // 6. Refresh flow
  const handleRefreshAccount = async (account: SocialAccount) => {
    try {
      setRefreshingAccountId(account.id);
      const res = await refreshSocialAccount(account.id);

      setToast({
        id: `refresh-${account.id}`,
        type: "success",
        title: "Connection refreshed",
        description: res.message || `${account.platform} connection is verified and healthy.`,
      });

      // Update in local state
      setAccounts((prev) =>
        prev.map((acc) => (acc.id === account.id ? res.account : acc))
      );
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Token refresh failed with provider";
      setToast({
        id: `refresh-err-${account.id}`,
        type: "error",
        title: "Refresh failed",
        description: msg,
      });
      // Optionally reload accounts to reflect ERROR status if backend updated it
      if (selectedCompanyId) {
        loadAccounts(selectedCompanyId);
      }
    } finally {
      setRefreshingAccountId(null);
    }
  };

  const currentCompany = companies.find((c) => c.id === selectedCompanyId);
  const filteredAccounts =
    platformFilter === "ALL"
      ? accounts
      : accounts.filter((a) => a.platform === platformFilter);

  return (
    <div className="min-h-screen bg-canvas text-gray-200 p-4 sm:p-6 lg:p-8 space-y-6 max-w-7xl mx-auto">
      {/* Toast Notification Banner */}
      <OAuthToastBanner toast={toast} onDismiss={() => setToast(null)} />

      {/* Top Header: Title, Description & Company Selector */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-borderSubtle pb-6">
        <div>
          <div className="flex items-center gap-2.5">
            <h1 className="text-2xl font-bold text-white tracking-tight" data-testid="page-title">
              Social Accounts
            </h1>
            <span className="px-2 py-0.5 text-xs font-mono bg-brandPrimary/10 text-brandPrimary border border-brandPrimary/30 rounded">
              Channel Manager
            </span>
          </div>
          <p className="text-xs sm:text-sm text-gray-400 mt-1 max-w-2xl">
            Manage authorized social connections for your brands. Tokens are encrypted using AES-256-GCM.
          </p>
        </div>

        {/* Brand Context Switcher */}
        <div className="flex items-center gap-3">
          <CompanySelector
            companies={companies}
            selectedCompanyId={selectedCompanyId}
            onSelectCompany={(newId) => setSelectedCompanyId(newId)}
            isLoading={isLoadingCompanies}
          />
          <button
            onClick={() => setIsConnectDialogOpen(true)}
            className="inline-flex items-center gap-1.5 py-2 px-3.5 rounded-lg text-xs font-semibold text-white bg-brandPrimary hover:bg-indigo-600 transition-all shadow-md shadow-indigo-950/40"
            data-testid="header-connect-account-btn"
          >
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 4v16m8-8H4" />
            </svg>
            Connect Account
          </button>
        </div>
      </div>

      {/* View Tabs & Platform Filters */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pt-1">
        {/* Tabs: Connected Accounts vs Available Providers */}
        <div className="flex items-center p-1 rounded-xl bg-surface border border-borderSubtle w-fit" role="tablist">
          <button
            role="tab"
            aria-selected={activeTab === "accounts"}
            onClick={() => setActiveTab("accounts")}
            className={`flex items-center gap-2 px-3.5 py-1.5 rounded-lg text-xs font-medium transition-all ${
              activeTab === "accounts"
                ? "bg-surfaceCard text-white shadow-sm border border-borderSubtle"
                : "text-gray-400 hover:text-gray-200"
            }`}
            data-testid="tab-connected-accounts"
          >
            Connected Accounts
            <span className="px-1.5 py-0.2 rounded-full text-[11px] font-mono bg-surface border border-borderSubtle text-gray-300">
              {accounts.length}
            </span>
          </button>

          <button
            role="tab"
            aria-selected={activeTab === "providers"}
            onClick={() => setActiveTab("providers")}
            className={`flex items-center gap-2 px-3.5 py-1.5 rounded-lg text-xs font-medium transition-all ${
              activeTab === "providers"
                ? "bg-surfaceCard text-white shadow-sm border border-borderSubtle"
                : "text-gray-400 hover:text-gray-200"
            }`}
            data-testid="tab-providers"
          >
            Add Integrations
            <span className="px-1.5 py-0.2 rounded-full text-[11px] font-mono bg-surface border border-borderSubtle text-gray-300">
              {PROVIDERS_LIST.length}
            </span>
          </button>
        </div>

        {/* Filter by Platform (Only visible in 'accounts' tab) */}
        {activeTab === "accounts" && accounts.length > 0 && (
          <div className="flex items-center gap-1.5 overflow-x-auto pb-1 sm:pb-0" data-testid="platform-filters">
            {["ALL", "INSTAGRAM", "FACEBOOK", "LINKEDIN", "YOUTUBE"].map((platform) => (
              <button
                key={platform}
                onClick={() => setPlatformFilter(platform)}
                className={`px-2.5 py-1 rounded-lg text-xs font-mono transition-colors ${
                  platformFilter === platform
                    ? "bg-brandPrimary/20 text-brandPrimary border border-brandPrimary/40"
                    : "bg-surface text-gray-400 border border-borderSubtle hover:text-gray-200"
                }`}
                data-testid={`filter-${platform.toLowerCase()}`}
              >
                {platform}
              </button>
            ))}
          </div>
        )}
      </div>

      {/* Main Content Area */}
      {activeTab === "accounts" ? (
        <div>
          {isLoadingAccounts ? (
            <AccountSkeleton count={3} />
          ) : accountsError ? (
            <AccountErrorState
              message={accountsError}
              onRetry={() => selectedCompanyId && loadAccounts(selectedCompanyId)}
            />
          ) : accounts.length === 0 ? (
            <AccountEmptyState
              companyName={currentCompany?.name}
              onConnectClick={() => setIsConnectDialogOpen(true)}
            />
          ) : filteredAccounts.length === 0 ? (
            <div className="p-8 rounded-xl bg-surfaceCard border border-borderSubtle text-center text-xs text-gray-400 space-y-2">
              <p>No accounts found matching platform filter: <span className="font-mono text-gray-200">{platformFilter}</span></p>
              <button
                onClick={() => setPlatformFilter("ALL")}
                className="text-brandPrimary hover:underline"
              >
                Clear filter
              </button>
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4" data-testid="accounts-grid">
              {filteredAccounts.map((account) => (
                <SocialAccountCard
                  key={account.id}
                  account={account}
                  companyName={currentCompany?.name}
                  isRefreshing={refreshingAccountId === account.id}
                  onRefresh={handleRefreshAccount}
                  onDisconnectClick={(acc) => setDisconnectTarget(acc)}
                />
              ))}
            </div>
          )}
        </div>
      ) : (
        /* Providers Integration Grid */
        <div className="space-y-4">
          <div className="p-4 rounded-xl bg-surface border border-borderSubtle text-xs text-gray-400 flex items-center justify-between">
            <span>
              Select a social network to connect to{" "}
              <strong className="text-white">{currentCompany?.name || "your brand"}</strong>.
            </span>
            <span className="font-mono text-[11px] text-emerald-400">OAuth 2.0 PKCE / AEAD</span>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-2 gap-4" data-testid="providers-grid">
            {PROVIDERS_LIST.map((provider) => {
              const connected = accounts.filter((a) => a.platform === provider.platform);
              return (
                <ProviderCard
                  key={provider.platform}
                  provider={provider}
                  connectedAccounts={connected}
                  isConnecting={connectingPlatform === provider.platform}
                  onConnect={handleConnectStart}
                />
              );
            })}
          </div>
        </div>
      )}

      {/* Disconnect Confirmation Dialog */}
      <DisconnectAccountDialog
        isOpen={Boolean(disconnectTarget)}
        account={disconnectTarget}
        companyName={currentCompany?.name}
        isDisconnecting={isDisconnecting}
        onConfirm={handleConfirmDisconnect}
        onClose={() => !isDisconnecting && setDisconnectTarget(null)}
      />

      {/* Connect Account Modal */}
      <ConnectAccountDialog
        isOpen={isConnectDialogOpen}
        companyName={currentCompany?.name || "Selected Brand"}
        isConnecting={Boolean(connectingPlatform)}
        connectingPlatform={connectingPlatform}
        onConnect={handleConnectStart}
        onClose={() => !connectingPlatform && setIsConnectDialogOpen(false)}
      />
    </div>
  );
};
