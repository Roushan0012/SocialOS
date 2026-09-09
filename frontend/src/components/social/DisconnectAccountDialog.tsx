"use client";

import React, { useEffect } from "react";
import { SocialAccount } from "@/types";
import { PlatformIcon } from "./PlatformIcon";

interface DisconnectAccountDialogProps {
  isOpen: boolean;
  account: SocialAccount | null;
  companyName?: string;
  isDisconnecting: boolean;
  onConfirm: () => void;
  onClose: () => void;
}

export const DisconnectAccountDialog: React.FC<DisconnectAccountDialogProps> = ({
  isOpen,
  account,
  companyName,
  isDisconnecting,
  onConfirm,
  onClose,
}) => {
  // Close on Escape key press
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape" && isOpen && !isDisconnecting) {
        onClose();
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isOpen, isDisconnecting, onClose]);

  if (!isOpen || !account) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/75 backdrop-blur-sm animate-in fade-in duration-200"
      data-testid="disconnect-dialog-overlay"
      onClick={(e) => {
        if (e.target === e.currentTarget && !isDisconnecting) {
          onClose();
        }
      }}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="disconnect-dialog-title"
        className="w-full max-w-md bg-surface border border-borderSubtle rounded-xl p-6 shadow-2xl space-y-5 animate-in zoom-in-95 duration-150"
        data-testid="disconnect-dialog"
      >
        {/* Header Icon + Title */}
        <div className="flex items-start gap-3.5">
          <div className="p-2.5 rounded-full bg-rose-950/60 border border-rose-800/60 text-rose-400 flex-shrink-0">
            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth="2"
                d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"
              />
            </svg>
          </div>
          <div>
            <h2 id="disconnect-dialog-title" className="text-base font-semibold text-white">
              Disconnect {account.platform} Account?
            </h2>
            <p className="mt-1 text-xs text-gray-400 leading-relaxed">
              Are you sure you want to disconnect{" "}
              <span className="text-white font-medium">@{account.account_name}</span> from{" "}
              <span className="text-gray-200 font-medium">{companyName || "this company"}</span>?
            </p>
          </div>
        </div>

        {/* Warning Explanation Box */}
        <div className="p-3.5 rounded-lg bg-surfaceCard border border-borderSubtle text-xs text-amber-300/90 leading-relaxed space-y-1.5">
          <p className="font-semibold flex items-center gap-1.5 text-amber-400">
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            What happens next:
          </p>
          <p className="text-gray-300">
            Stored access credentials will be securely wiped. Scheduled publishing for this account may stop working once disconnected.
          </p>
        </div>

        {/* Account Info Pill */}
        <div className="flex items-center gap-2 p-2 rounded-lg bg-surfaceCard border border-borderSubtle/60 text-xs font-mono">
          <PlatformIcon platform={account.platform} className="w-4 h-4 text-gray-400" />
          <span className="text-gray-200 font-medium">{account.account_name}</span>
          <span className="text-gray-500 truncate ml-auto">({account.platform_account_id})</span>
        </div>

        {/* Action Buttons */}
        <div className="flex items-center justify-end gap-3 pt-2">
          <button
            type="button"
            onClick={onClose}
            disabled={isDisconnecting}
            className="py-2 px-4 rounded-lg text-xs font-medium text-gray-300 hover:text-white bg-surfaceCard hover:bg-gray-800 border border-borderSubtle transition-colors disabled:opacity-50"
            data-testid="disconnect-cancel-button"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={onConfirm}
            disabled={isDisconnecting}
            className="py-2 px-4 rounded-lg text-xs font-semibold text-white bg-rose-600 hover:bg-rose-700 shadow-md shadow-rose-950/50 flex items-center gap-2 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            data-testid="disconnect-confirm-button"
          >
            {isDisconnecting ? (
              <>
                <svg
                  className="animate-spin h-3.5 w-3.5 text-white"
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
                Disconnecting...
              </>
            ) : (
              "Disconnect Account"
            )}
          </button>
        </div>
      </div>
    </div>
  );
};
