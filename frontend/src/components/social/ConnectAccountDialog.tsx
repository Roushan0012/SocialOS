"use client";

import React, { useEffect } from "react";
import { Platform } from "@/types";
import { PlatformIcon } from "./PlatformIcon";
import { PROVIDERS_LIST } from "./ProviderCard";

interface ConnectAccountDialogProps {
  isOpen: boolean;
  companyName: string;
  isConnecting: boolean;
  connectingPlatform: Platform | null;
  onConnect: (platform: Platform) => void;
  onClose: () => void;
}

export const ConnectAccountDialog: React.FC<ConnectAccountDialogProps> = ({
  isOpen,
  companyName,
  isConnecting,
  connectingPlatform,
  onConnect,
  onClose,
}) => {
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape" && isOpen && !isConnecting) {
        onClose();
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isOpen, isConnecting, onClose]);

  if (!isOpen) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/75 backdrop-blur-sm animate-in fade-in duration-200"
      data-testid="connect-dialog-overlay"
      onClick={(e) => {
        if (e.target === e.currentTarget && !isConnecting) {
          onClose();
        }
      }}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="connect-dialog-title"
        className="w-full max-w-lg bg-surface border border-borderSubtle rounded-xl p-6 shadow-2xl space-y-5 animate-in zoom-in-95 duration-150"
        data-testid="connect-dialog"
      >
        {/* Header */}
        <div className="flex items-start justify-between border-b border-borderSubtle pb-4">
          <div>
            <h2 id="connect-dialog-title" className="text-lg font-semibold text-white tracking-tight">
              Connect a Social Account
            </h2>
            <p className="mt-1 text-xs text-gray-400">
              Select an official social network to connect to{" "}
              <span className="text-brandPrimary font-medium">{companyName}</span>.
            </p>
          </div>
          <button
            onClick={onClose}
            disabled={isConnecting}
            className="text-gray-500 hover:text-gray-300 p-1 rounded-md transition-colors"
            data-testid="connect-dialog-close"
          >
            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        {/* Security Notice */}
        <div className="p-3 rounded-lg bg-surfaceCard border border-borderSubtle text-xs text-gray-400 space-y-1">
          <div className="flex items-center gap-1.5 text-emerald-400 font-medium">
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" />
            </svg>
            OAuth 2.0 Security
          </div>
          <p>
            You will be securely redirected to the external provider. SocialOS uses AES-256-GCM encryption at rest and never stores passwords.
          </p>
        </div>

        {/* Providers Grid */}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          {PROVIDERS_LIST.map((provider) => {
            const isThisConnecting = isConnecting && connectingPlatform === provider.platform;

            return (
              <button
                key={provider.platform}
                onClick={() => onConnect(provider.platform)}
                disabled={isConnecting}
                className="flex items-start gap-3 p-3.5 rounded-xl bg-surfaceCard border border-borderSubtle hover:border-gray-600 transition-all text-left group disabled:opacity-50 disabled:cursor-not-allowed shadow-sm"
                data-testid={`dialog-provider-button-${provider.platform.toLowerCase()}`}
              >
                <div
                  className={`p-2 rounded-lg ${provider.badgeBg} ${provider.badgeColor} border border-borderSubtle flex-shrink-0`}
                >
                  <PlatformIcon platform={provider.platform} className="w-5 h-5" />
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center justify-between">
                    <span className="text-sm font-semibold text-white group-hover:text-brandPrimary transition-colors">
                      {provider.name}
                    </span>
                    {isThisConnecting && (
                      <svg
                        className="animate-spin h-3.5 w-3.5 text-brandPrimary"
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
                    )}
                  </div>
                  <p className="text-[11px] text-gray-400 line-clamp-2 mt-0.5">
                    {provider.features.join(" • ")}
                  </p>
                </div>
              </button>
            );
          })}
        </div>

        {/* Footer */}
        <div className="flex items-center justify-end pt-3 border-t border-borderSubtle">
          <button
            type="button"
            onClick={onClose}
            disabled={isConnecting}
            className="py-2 px-4 rounded-lg text-xs font-medium text-gray-400 hover:text-white transition-colors"
          >
            Cancel
          </button>
        </div>
      </div>
    </div>
  );
};
