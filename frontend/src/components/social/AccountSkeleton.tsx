"use client";

import React from "react";

export const AccountSkeleton: React.FC<{ count?: number }> = ({ count = 3 }) => {
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4" data-testid="accounts-loading-skeleton">
      {Array.from({ length: count }).map((_, idx) => (
        <div
          key={idx}
          className="p-5 rounded-xl bg-surfaceCard border border-borderSubtle animate-pulse space-y-4"
        >
          {/* Top Bar Skeleton */}
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="w-9 h-9 rounded-lg bg-surface border border-borderSubtle" />
              <div className="space-y-1.5">
                <div className="w-16 h-3 bg-gray-800 rounded" />
                <div className="w-24 h-4 bg-gray-700 rounded" />
              </div>
            </div>
            <div className="w-20 h-5 bg-gray-800 rounded-full" />
          </div>

          {/* Details Box Skeleton */}
          <div className="p-3 rounded-lg bg-surface space-y-2">
            <div className="flex justify-between">
              <div className="w-16 h-3 bg-gray-800 rounded" />
              <div className="w-20 h-3 bg-gray-700 rounded" />
            </div>
            <div className="flex justify-between">
              <div className="w-12 h-3 bg-gray-800 rounded" />
              <div className="w-28 h-3 bg-gray-700 rounded" />
            </div>
            <div className="flex justify-between">
              <div className="w-14 h-3 bg-gray-800 rounded" />
              <div className="w-24 h-3 bg-gray-700 rounded" />
            </div>
          </div>

          {/* Action Buttons Skeleton */}
          <div className="pt-4 border-t border-borderSubtle flex gap-2">
            <div className="flex-1 h-8 bg-surface rounded-lg" />
            <div className="w-20 h-8 bg-surface rounded-lg" />
          </div>
        </div>
      ))}
    </div>
  );
};
