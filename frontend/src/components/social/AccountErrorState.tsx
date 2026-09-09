"use client";

import React from "react";

interface AccountErrorStateProps {
  message: string;
  onRetry: () => void;
}

export const AccountErrorState: React.FC<AccountErrorStateProps> = ({
  message,
  onRetry,
}) => {
  return (
    <div
      className="p-8 rounded-xl bg-surfaceCard border border-rose-900/40 text-center flex flex-col items-center justify-center space-y-3 shadow-xl"
      data-testid="accounts-error-state"
    >
      <div className="w-12 h-12 rounded-full bg-rose-950/60 border border-rose-800/60 flex items-center justify-center text-rose-400">
        <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth="2"
            d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
          />
        </svg>
      </div>

      <div className="space-y-1 max-w-md">
        <h3 className="text-sm font-semibold text-white tracking-tight">
          Unable to Load Social Accounts
        </h3>
        <p className="text-xs text-rose-300/90 leading-relaxed font-mono">
          {message}
        </p>
      </div>

      <div className="pt-2">
        <button
          onClick={onRetry}
          className="inline-flex items-center gap-1.5 py-1.5 px-4 rounded-lg text-xs font-semibold text-gray-200 bg-surface hover:bg-gray-800 border border-borderSubtle transition-colors"
          data-testid="error-state-retry-button"
        >
          <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth="2"
              d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"
            />
          </svg>
          Retry
        </button>
      </div>
    </div>
  );
};
