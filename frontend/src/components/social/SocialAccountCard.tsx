"use client";

import React from "react";
import { SocialAccount } from "@/types";
import { AccountStatusBadge } from "./AccountStatusBadge";
import { PlatformIcon } from "./PlatformIcon";

interface SocialAccountCardProps {
  account: SocialAccount;
  companyName?: string;
  isRefreshing: boolean;
  onRefresh: (account: SocialAccount) => void;
  onDisconnectClick: (account: SocialAccount) => void;
}

export const SocialAccountCard: React.FC<SocialAccountCardProps> = ({
  account,
  companyName,
  isRefreshing,
  onRefresh,
  onDisconnectClick,
}) => {
  const formatDate = (isoString?: string | null): string => {
    if (!isoString) return "Never";
    try {
      const date = new Date(isoString);
      return new Intl.DateTimeFormat("en-US", {
        month: "short",
        day: "numeric",
        year: "numeric",
        hour: "numeric",
        minute: "numeric",
      }).format(date);
    } catch {
      return isoString;
    }
  };

  const getPlatformBorder = (platform: string): string => {
    switch (platform) {
      case "INSTAGRAM":
        return "hover:border-pink-500/40";
      case "FACEBOOK":
        return "hover:border-blue-500/40";
      case "LINKEDIN":
        return "hover:border-sky-500/40";
      case "YOUTUBE":
        return "hover:border-red-500/40";
      default:
        return "hover:border-gray-500/40";
    }
  };

  return (
    <div
      className={`p-5 rounded-xl bg-surfaceCard border border-borderSubtle transition-all duration-200 shadow-lg flex flex-col justify-between ${getPlatformBorder(
        account.platform
      )}`}
      data-testid={`social-account-card-${account.id}`}
    >
      <div className="space-y-4">
        {/* Top bar: Platform Icon + Status */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <div className="p-2 rounded-lg bg-surface border border-borderSubtle text-gray-200">
              <PlatformIcon platform={account.platform} className="w-5 h-5" />
            </div>
            <div>
              <span className="text-xs font-mono font-medium text-gray-400 uppercase">
                {account.platform}
              </span>
              <p className="text-sm font-semibold text-white tracking-tight leading-none">
                {account.account_name}
              </p>
            </div>
          </div>
          <AccountStatusBadge status={account.status} />
        </div>

        {/* Metadata Details */}
        <div className="p-3 rounded-lg bg-surface border border-borderSubtle/60 text-xs space-y-2 font-mono">
          <div className="flex items-center justify-between text-gray-400">
            <span>Account ID:</span>
            <span className="text-gray-200 truncate max-w-[150px]" title={account.platform_account_id}>
              {account.platform_account_id}
            </span>
          </div>

          {companyName && (
            <div className="flex items-center justify-between text-gray-400">
              <span>Brand:</span>
              <span className="text-gray-200">{companyName}</span>
            </div>
          )}

          <div className="flex items-center justify-between text-gray-400">
            <span>Connected:</span>
            <span className="text-gray-200">{formatDate(account.last_connected_at || account.created_at)}</span>
          </div>

          {account.token_expires_at && (
            <div className="flex items-center justify-between text-gray-400">
              <span>Expires:</span>
              <span className="text-gray-300">{formatDate(account.token_expires_at)}</span>
            </div>
          )}
        </div>
      </div>

      {/* Action buttons */}
      <div className="mt-5 pt-4 border-t border-borderSubtle flex items-center justify-between gap-2">
        <button
          onClick={() => onRefresh(account)}
          disabled={isRefreshing}
          className="flex-1 inline-flex items-center justify-center gap-1.5 py-1.5 px-3 rounded-lg text-xs font-medium text-gray-300 bg-surface hover:bg-surfaceCard hover:text-white border border-borderSubtle hover:border-gray-600 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          data-testid={`refresh-button-${account.id}`}
        >
          {isRefreshing ? (
            <>
              <svg
                className="animate-spin h-3.5 w-3.5 text-current"
                xmlns="http://www.w3.org/2000/svg"
                fill="none"
                viewBox="0 0 24 24"
              >
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                <path
                  className="opacity-75"
                  fill="currentColor"
                  d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
                />
              </svg>
              Refreshing...
            </>
          ) : (
            <>
              <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth="2"
                  d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"
                />
              </svg>
              Refresh
            </>
          )}
        </button>

        <button
          onClick={() => onDisconnectClick(account)}
          disabled={isRefreshing}
          className="inline-flex items-center justify-center gap-1 py-1.5 px-3 rounded-lg text-xs font-medium text-rose-400 bg-rose-950/30 hover:bg-rose-950/60 border border-rose-900/40 hover:border-rose-700/60 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          data-testid={`disconnect-button-${account.id}`}
        >
          <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth="2"
              d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"
            />
          </svg>
          Disconnect
        </button>
      </div>
    </div>
  );
};
