"use client";

import React, { useEffect } from "react";

export type ToastType = "success" | "error" | "info";

export interface ToastMessage {
  id: string;
  type: ToastType;
  title: string;
  description?: string;
}

interface OAuthToastBannerProps {
  toast: ToastMessage | null;
  onDismiss: () => void;
  autoDismissMs?: number;
}

export const OAuthToastBanner: React.FC<OAuthToastBannerProps> = ({
  toast,
  onDismiss,
  autoDismissMs = 6000,
}) => {
  useEffect(() => {
    if (!toast) return;
    const timer = setTimeout(() => {
      onDismiss();
    }, autoDismissMs);
    return () => clearTimeout(timer);
  }, [toast, onDismiss, autoDismissMs]);

  if (!toast) return null;

  const isSuccess = toast.type === "success";
  const isError = toast.type === "error";

  return (
    <div
      role="alert"
      aria-live="polite"
      className={`p-4 rounded-xl border transition-all duration-300 flex items-start justify-between gap-3 shadow-2xl animate-in slide-in-from-top-3 ${
        isSuccess
          ? "bg-emerald-950/70 border-emerald-800/80 text-emerald-300"
          : isError
          ? "bg-rose-950/70 border-rose-800/80 text-rose-300"
          : "bg-surfaceCard border-borderSubtle text-gray-200"
      }`}
      data-testid={`toast-${toast.type}`}
    >
      <div className="flex items-start gap-3">
        <div className="pt-0.5">
          {isSuccess && (
            <svg className="w-5 h-5 text-emerald-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M5 13l4 4L19 7" />
            </svg>
          )}
          {isError && (
            <svg className="w-5 h-5 text-rose-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M6 18L18 6M6 6l12 12" />
            </svg>
          )}
        </div>
        <div>
          <h4 className="text-sm font-semibold text-white tracking-tight leading-snug">
            {toast.title}
          </h4>
          {toast.description && (
            <p className="mt-0.5 text-xs opacity-90 leading-relaxed font-sans">
              {toast.description}
            </p>
          )}
        </div>
      </div>

      <button
        onClick={onDismiss}
        className="text-gray-400 hover:text-white p-1 rounded-md transition-colors"
        aria-label="Dismiss notification"
        data-testid="toast-dismiss-button"
      >
        <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M6 18L18 6M6 6l12 12" />
        </svg>
      </button>
    </div>
  );
};
