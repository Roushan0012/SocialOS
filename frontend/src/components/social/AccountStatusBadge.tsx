"use client";

import React from "react";
import { SocialAccountStatus } from "@/types";

interface AccountStatusBadgeProps {
  status: SocialAccountStatus;
  className?: string;
}

export const AccountStatusBadge: React.FC<AccountStatusBadgeProps> = ({
  status,
  className = "",
}) => {
  switch (status) {
    case "ACTIVE":
      return (
        <span
          className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-medium bg-emerald-950/60 text-emerald-400 border border-emerald-800/50 ${className}`}
          data-testid="status-badge-active"
        >
          <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
          Connected
        </span>
      );
    case "DISCONNECTED":
      return (
        <span
          className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-medium bg-gray-900/60 text-gray-400 border border-gray-700/50 ${className}`}
          data-testid="status-badge-disconnected"
        >
          <span className="w-1.5 h-1.5 rounded-full bg-gray-500" />
          Disconnected
        </span>
      );
    case "EXPIRED":
      return (
        <span
          className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-medium bg-amber-950/60 text-amber-400 border border-amber-800/50 ${className}`}
          data-testid="status-badge-expired"
        >
          <span className="w-1.5 h-1.5 rounded-full bg-amber-400" />
          Needs Attention
        </span>
      );
    case "ERROR":
      return (
        <span
          className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-medium bg-rose-950/60 text-rose-400 border border-rose-800/50 ${className}`}
          data-testid="status-badge-error"
        >
          <span className="w-1.5 h-1.5 rounded-full bg-rose-400" />
          Connection Error
        </span>
      );
    default:
      return null;
  }
};
