"use client";

import React from "react";

interface AccountEmptyStateProps {
  companyName?: string;
  onConnectClick: () => void;
}

export const AccountEmptyState: React.FC<AccountEmptyStateProps> = ({
  companyName,
  onConnectClick,
}) => {
  return (
    <div
      className="p-12 rounded-xl bg-surfaceCard border border-borderSubtle text-center flex flex-col items-center justify-center space-y-4 shadow-xl"
      data-testid="accounts-empty-state"
    >
      <div className="w-14 h-14 rounded-2xl bg-surface border border-borderSubtle flex items-center justify-center text-gray-500 shadow-inner">
        <svg
          className="w-7 h-7 text-brandPrimary"
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
          strokeWidth="1.75"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            d="M13.828 10.172a4 4 0 00-5.656 0l-4 4a4 4 0 105.656 5.656l1.102-1.101m-.758-4.899a4 4 0 005.656 0l4-4a4 4 0 00-5.656-5.656l-1.1 1.1"
          />
        </svg>
      </div>

      <div className="max-w-md space-y-1.5">
        <h3 className="text-base font-semibold text-white tracking-tight">
          No social accounts connected yet
        </h3>
        <p className="text-xs text-gray-400 leading-relaxed">
          {companyName ? (
            <>
              Connect social media accounts to{" "}
              <span className="text-gray-200 font-medium">{companyName}</span> to enable
              authorized channel access.
            </>
          ) : (
            "Select a brand and connect an Instagram, Facebook, LinkedIn, or YouTube profile to begin."
          )}
        </p>
      </div>

      <div className="pt-2">
        <button
          onClick={onConnectClick}
          className="inline-flex items-center gap-2 py-2 px-4 rounded-lg text-xs font-semibold text-white bg-brandPrimary hover:bg-indigo-600 transition-all shadow-md shadow-indigo-950/50 hover:scale-[1.02] active:scale-[0.98]"
          data-testid="empty-state-connect-button"
        >
          <svg
            className="w-4 h-4"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
            strokeWidth="2"
          >
            <path strokeLinecap="round" strokeLinejoin="round" d="M12 4v16m8-8H4" />
          </svg>
          Connect Account
        </button>
      </div>
    </div>
  );
};
