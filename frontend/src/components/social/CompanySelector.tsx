"use client";

import React from "react";
import { Company } from "@/types";

interface CompanySelectorProps {
  companies: Company[];
  selectedCompanyId: string | null;
  onSelectCompany: (companyId: string) => void;
  isLoading?: boolean;
}

export const CompanySelector: React.FC<CompanySelectorProps> = ({
  companies,
  selectedCompanyId,
  onSelectCompany,
  isLoading = false,
}) => {
  if (isLoading) {
    return (
      <div className="h-9 w-48 bg-surface rounded-lg border border-borderSubtle animate-pulse" />
    );
  }

  if (companies.length === 0) {
    return (
      <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-surface border border-borderSubtle text-xs text-gray-400">
        <span>No brand workspaces found</span>
      </div>
    );
  }

  const selectedCompany = companies.find((c) => c.id === selectedCompanyId) || companies[0];

  return (
    <div className="flex items-center gap-2.5" data-testid="company-selector-container">
      <label htmlFor="company-select" className="text-xs font-mono uppercase text-gray-500 hidden sm:inline">
        Active Brand:
      </label>
      <div className="relative">
        <select
          id="company-select"
          value={selectedCompanyId || (selectedCompany ? selectedCompany.id : "")}
          onChange={(e) => onSelectCompany(e.target.value)}
          className="appearance-none bg-surfaceCard text-gray-200 text-xs font-medium pl-8 pr-8 py-2 rounded-lg border border-borderSubtle hover:border-gray-600 focus:outline-none focus:ring-2 focus:ring-brandPrimary/50 transition-colors cursor-pointer"
          data-testid="company-select-dropdown"
        >
          {companies.map((company) => (
            <option key={company.id} value={company.id} className="bg-surface text-white">
              {company.name}
            </option>
          ))}
        </select>
        {/* Brand Icon left */}
        <div className="absolute left-2.5 top-1/2 -translate-y-1/2 pointer-events-none text-gray-400">
          <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth="2"
              d="M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4"
            />
          </svg>
        </div>
        {/* Caret icon right */}
        <div className="absolute right-2.5 top-1/2 -translate-y-1/2 pointer-events-none text-gray-400">
          <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M19 9l-7 7-7-7" />
          </svg>
        </div>
      </div>
    </div>
  );
};
