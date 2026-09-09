"use client";

import React from "react";
import { Platform, SocialAccount } from "@/types";
import { PlatformIcon } from "./PlatformIcon";

export interface ProviderDefinition {
  platform: Platform;
  name: string;
  description: string;
  badgeColor: string;
  badgeBg: string;
  borderColor: string;
  features: string[];
}

export const PROVIDERS_LIST: ProviderDefinition[] = [
  {
    platform: "INSTAGRAM",
    name: "Instagram",
    description:
      "Connect your Instagram Business or Creator profile to publish content, reels, and view audience engagement.",
    badgeColor: "text-pink-400",
    badgeBg: "bg-pink-950/40",
    borderColor: "border-pink-900/40 hover:border-pink-500/50",
    features: ["Photo & Carousel Posts", "Instagram Reels", "Audience Analytics"],
  },
  {
    platform: "FACEBOOK",
    name: "Facebook",
    description:
      "Connect Meta Pages to manage multi-format posts, page updates, and unified audience engagement.",
    badgeColor: "text-blue-400",
    badgeBg: "bg-blue-950/40",
    borderColor: "border-blue-900/40 hover:border-blue-500/50",
    features: ["Page Feed Posts", "Video & Stories", "Community Engagement"],
  },
  {
    platform: "LINKEDIN",
    name: "LinkedIn",
    description:
      "Connect LinkedIn Company Pages or member profiles for B2B thought leadership and professional updates.",
    badgeColor: "text-sky-400",
    badgeBg: "bg-sky-950/40",
    borderColor: "border-sky-900/40 hover:border-sky-500/50",
    features: ["Company Page Articles", "Image & Document Posts", "B2B Analytics"],
  },
  {
    platform: "YOUTUBE",
    name: "YouTube",
    description:
      "Connect your official YouTube Channel to manage Shorts, video publications, and channel metadata.",
    badgeColor: "text-red-400",
    badgeBg: "bg-red-950/40",
    borderColor: "border-red-900/40 hover:border-red-500/50",
    features: ["YouTube Shorts", "Video Dispatch", "Channel Metrics"],
  },
];

interface ProviderCardProps {
  provider: ProviderDefinition;
  connectedAccounts: SocialAccount[];
  isConnecting: boolean;
  onConnect: (platform: Platform) => void;
}

export const ProviderCard: React.FC<ProviderCardProps> = ({
  provider,
  connectedAccounts,
  isConnecting,
  onConnect,
}) => {
  const isConnected = connectedAccounts.length > 0;

  return (
    <div
      className={`flex flex-col justify-between p-5 rounded-xl bg-surfaceCard border ${provider.borderColor} transition-all duration-200 shadow-lg`}
      data-testid={`provider-card-${provider.platform.toLowerCase()}`}
    >
      <div className="space-y-4">
        {/* Header: Icon & Status */}
        <div className="flex items-start justify-between">
          <div
            className={`p-2.5 rounded-lg ${provider.badgeBg} ${provider.badgeColor} border border-borderSubtle`}
          >
            <PlatformIcon platform={provider.platform} className="w-6 h-6" />
          </div>
          {isConnected ? (
            <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-medium bg-emerald-950/60 text-emerald-400 border border-emerald-800/50">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-400" />
              Connected ({connectedAccounts.length})
            </span>
          ) : (
            <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs text-gray-500 bg-gray-900/80 border border-gray-800">
              Available
            </span>
          )}
        </div>

        {/* Title & Description */}
        <div>
          <h3 className="text-base font-semibold text-white tracking-tight">
            {provider.name}
          </h3>
          <p className="mt-1 text-xs text-gray-400 leading-relaxed">
            {provider.description}
          </p>
        </div>

        {/* Capabilities list */}
        <div className="pt-2 border-t border-borderSubtle/60">
          <span className="text-[11px] font-mono text-gray-500 uppercase tracking-wider">
            Capabilities
          </span>
          <ul className="mt-1.5 space-y-1">
            {provider.features.map((feature, idx) => (
              <li
                key={idx}
                className="flex items-center text-xs text-gray-300 gap-1.5"
              >
                <svg
                  className="w-3.5 h-3.5 text-emerald-400 flex-shrink-0"
                  fill="none"
                  viewBox="0 0 24 24"
                  stroke="currentColor"
                  strokeWidth="2.5"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    d="M5 13l4 4L19 7"
                  />
                </svg>
                {feature}
              </li>
            ))}
          </ul>
        </div>
      </div>

      {/* Action Footer */}
      <div className="mt-6 pt-4 border-t border-borderSubtle">
        <button
          onClick={() => onConnect(provider.platform)}
          disabled={isConnecting}
          className={`w-full flex items-center justify-center gap-2 py-2 px-4 rounded-lg text-xs font-semibold transition-colors focus:outline-none focus:ring-2 focus:ring-brandPrimary/50 ${
            isConnected
              ? "bg-surface hover:bg-surfaceCard text-gray-200 border border-borderSubtle hover:border-gray-600"
              : "bg-brandPrimary hover:bg-indigo-600 text-white shadow-md shadow-indigo-950/50"
          } disabled:opacity-50 disabled:cursor-not-allowed`}
          data-testid={`connect-button-${provider.platform.toLowerCase()}`}
        >
          {isConnecting ? (
            <>
              <svg
                className="animate-spin h-3.5 w-3.5 text-current"
                xmlns="http://www.w3.org/2000/svg"
                fill="none"
                viewBox="0 0 24 24"
              >
                <circle
                  className="opacity-25"
                  cx="12"
                  cy="12"
                  r="10"
                  stroke="currentColor"
                  strokeWidth="4"
                />
                <path
                  className="opacity-75"
                  fill="currentColor"
                  d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
                />
              </svg>
              Redirecting...
            </>
          ) : isConnected ? (
            `Reconnect ${provider.name}`
          ) : (
            `Connect ${provider.name}`
          )}
        </button>
      </div>
    </div>
  );
};
