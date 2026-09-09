import React from "react";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { SocialAccountsView } from "../SocialAccountsView";
import * as api from "@/lib/api";
import { Company, SocialAccount } from "@/types";

// Mock the API module
vi.mock("@/lib/api", () => ({
  getCompanies: vi.fn(),
  getSocialAccounts: vi.fn(),
  startOAuthFlow: vi.fn(),
  disconnectSocialAccount: vi.fn(),
  refreshSocialAccount: vi.fn(),
}));

const mockCompanies: Company[] = [
  {
    id: "comp-111",
    name: "Acme Brand",
    slug: "acme-brand",
    is_active: true,
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
  },
  {
    id: "comp-222",
    name: "Stark Industries",
    slug: "stark-industries",
    is_active: true,
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
  },
];

const mockAccountsCompany1: SocialAccount[] = [
  {
    id: "acc-ig-1",
    company_id: "comp-111",
    platform: "INSTAGRAM",
    account_name: "acme_official",
    platform_account_id: "ig_17841400",
    status: "ACTIVE",
    token_expires_at: "2026-12-31T00:00:00Z",
    last_connected_at: "2026-09-01T12:00:00Z",
    created_at: "2026-09-01T12:00:00Z",
    updated_at: "2026-09-01T12:00:00Z",
  },
  {
    id: "acc-li-1",
    company_id: "comp-111",
    platform: "LINKEDIN",
    account_name: "Acme Corporation",
    platform_account_id: "li_998877",
    status: "ACTIVE",
    token_expires_at: null,
    last_connected_at: "2026-09-02T10:00:00Z",
    created_at: "2026-09-02T10:00:00Z",
    updated_at: "2026-09-02T10:00:00Z",
  },
];

const mockAccountsCompany2: SocialAccount[] = [
  {
    id: "acc-yt-2",
    company_id: "comp-222",
    platform: "YOUTUBE",
    account_name: "Stark Tech Channel",
    platform_account_id: "UC_STARK_123",
    status: "ACTIVE",
    token_expires_at: null,
    last_connected_at: "2026-09-05T08:00:00Z",
    created_at: "2026-09-05T08:00:00Z",
    updated_at: "2026-09-05T08:00:00Z",
  },
];

describe("SocialAccountsView Component", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(api.getCompanies).mockResolvedValue({
      items: mockCompanies,
      total: 2,
      page: 1,
      page_size: 50,
      total_pages: 1,
    });
    vi.mocked(api.getSocialAccounts).mockImplementation(async (companyId: string) => {
      if (companyId === "comp-111") return mockAccountsCompany1;
      if (companyId === "comp-222") return mockAccountsCompany2;
      return [];
    });
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("renders loading skeleton while fetching data", () => {
    // Return pending promise
    vi.mocked(api.getSocialAccounts).mockReturnValue(new Promise(() => {}));
    render(<SocialAccountsView initialCompanies={mockCompanies} initialSelectedCompanyId="comp-111" />);

    expect(screen.getByTestId("accounts-loading-skeleton")).toBeInTheDocument();
  });

  it("renders account list from API data", async () => {
    render(<SocialAccountsView initialCompanies={mockCompanies} initialSelectedCompanyId="comp-111" />);

    await waitFor(() => {
      expect(screen.getByText("acme_official")).toBeInTheDocument();
      expect(screen.getByText("Acme Corporation")).toBeInTheDocument();
    });

    expect(screen.getByTestId("social-account-card-acc-ig-1")).toBeInTheDocument();
    expect(screen.getByTestId("social-account-card-acc-li-1")).toBeInTheDocument();
    expect(screen.getAllByTestId("status-badge-active").length).toBe(2);
  });

  it("renders empty state when no accounts are connected to the selected company", async () => {
    vi.mocked(api.getSocialAccounts).mockResolvedValue([]);
    render(<SocialAccountsView initialCompanies={mockCompanies} initialSelectedCompanyId="comp-111" />);

    await waitFor(() => {
      expect(screen.getByTestId("accounts-empty-state")).toBeInTheDocument();
      expect(screen.getByText("No social accounts connected yet")).toBeInTheDocument();
      expect(screen.getByTestId("empty-state-connect-button")).toBeInTheDocument();
    });
  });

  it("renders error state and retries on user click", async () => {
    vi.mocked(api.getSocialAccounts)
      .mockRejectedValueOnce(new Error("Failed to connect to database"))
      .mockResolvedValueOnce(mockAccountsCompany1);

    render(<SocialAccountsView initialCompanies={mockCompanies} initialSelectedCompanyId="comp-111" />);

    await waitFor(() => {
      expect(screen.getByTestId("accounts-error-state")).toBeInTheDocument();
      expect(screen.getByText("Failed to connect to database")).toBeInTheDocument();
    });

    const retryBtn = screen.getByTestId("error-state-retry-button");
    fireEvent.click(retryBtn);

    await waitFor(() => {
      expect(screen.getByText("acme_official")).toBeInTheDocument();
    });
  });

  it("switching active company changes account query and reloads accounts", async () => {
    render(<SocialAccountsView initialCompanies={mockCompanies} initialSelectedCompanyId="comp-111" />);

    await waitFor(() => {
      expect(screen.getByText("acme_official")).toBeInTheDocument();
    });

    const dropdown = screen.getByTestId("company-select-dropdown");
    fireEvent.change(dropdown, { target: { value: "comp-222" } });

    await waitFor(() => {
      expect(screen.getByText("Stark Tech Channel")).toBeInTheDocument();
      expect(screen.queryByText("acme_official")).not.toBeInTheDocument();
    });

    expect(api.getSocialAccounts).toHaveBeenCalledWith("comp-222");
  });

  it("connect button calls startOAuthFlow and redirects user", async () => {
    vi.mocked(api.startOAuthFlow).mockResolvedValue({
      authorization_url: "https://api.instagram.com/oauth/authorize?mock=1",
      state: "mock_state_123",
      platform: "INSTAGRAM",
    });

    // Mock window.location
    const originalLocation = window.location;
    const mockLocation = { ...originalLocation, href: "" };
    Object.defineProperty(window, "location", {
      writable: true,
      configurable: true,
      value: mockLocation,
    });

    render(<SocialAccountsView initialCompanies={mockCompanies} initialSelectedCompanyId="comp-111" />);

    await waitFor(() => {
      expect(screen.getByText("acme_official")).toBeInTheDocument();
    });

    // Open connect dialog via header button
    fireEvent.click(screen.getByTestId("header-connect-account-btn"));
    expect(screen.getByTestId("connect-dialog")).toBeInTheDocument();

    // Click Instagram provider in dialog
    const instaBtn = screen.getByTestId("dialog-provider-button-instagram");
    fireEvent.click(instaBtn);

    await waitFor(() => {
      expect(api.startOAuthFlow).toHaveBeenCalledWith("INSTAGRAM", "comp-111");
      expect(window.location.href).toBe("https://api.instagram.com/oauth/authorize?mock=1");
    });

    Object.defineProperty(window, "location", {
      writable: true,
      configurable: true,
      value: originalLocation,
    });
  });

  it("disconnect flow opens confirmation dialog and successfully disconnects", async () => {
    vi.mocked(api.disconnectSocialAccount).mockResolvedValue({
      ...mockAccountsCompany1[0],
      status: "DISCONNECTED",
    });

    render(<SocialAccountsView initialCompanies={mockCompanies} initialSelectedCompanyId="comp-111" />);

    await waitFor(() => {
      expect(screen.getByText("acme_official")).toBeInTheDocument();
    });

    // Click disconnect on the first account
    fireEvent.click(screen.getByTestId("disconnect-button-acc-ig-1"));

    // Verify confirmation modal opened
    expect(screen.getByTestId("disconnect-dialog")).toBeInTheDocument();
    expect(
      screen.getByText(/Scheduled publishing for this account may stop working once disconnected/)
    ).toBeInTheDocument();

    // Confirm disconnect
    fireEvent.click(screen.getByTestId("disconnect-confirm-button"));

    await waitFor(() => {
      expect(api.disconnectSocialAccount).toHaveBeenCalledWith("acc-ig-1");
      expect(screen.getByText("Account disconnected")).toBeInTheDocument();
    });
  });

  it("failed disconnect shows error toast notification", async () => {
    vi.mocked(api.disconnectSocialAccount).mockRejectedValue(new Error("Permission denied"));

    render(<SocialAccountsView initialCompanies={mockCompanies} initialSelectedCompanyId="comp-111" />);

    await waitFor(() => {
      expect(screen.getByText("acme_official")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByTestId("disconnect-button-acc-ig-1"));
    fireEvent.click(screen.getByTestId("disconnect-confirm-button"));

    await waitFor(() => {
      expect(screen.getByText("Could not disconnect account")).toBeInTheDocument();
      expect(screen.getByText("Permission denied")).toBeInTheDocument();
    });
  });

  it("refresh connection flow calls refresh endpoint and updates account", async () => {
    const refreshedAccount: SocialAccount = {
      ...mockAccountsCompany1[1],
      last_connected_at: "2026-09-10T03:00:00Z",
      status: "ACTIVE",
    };

    vi.mocked(api.refreshSocialAccount).mockResolvedValue({
      message: "LINKEDIN token refreshed successfully",
      account: refreshedAccount,
    });

    render(<SocialAccountsView initialCompanies={mockCompanies} initialSelectedCompanyId="comp-111" />);

    await waitFor(() => {
      expect(screen.getByText("Acme Corporation")).toBeInTheDocument();
    });

    const refreshBtn = screen.getByTestId("refresh-button-acc-li-1");
    fireEvent.click(refreshBtn);

    await waitFor(() => {
      expect(api.refreshSocialAccount).toHaveBeenCalledWith("acc-li-1");
      expect(screen.getByText("Connection refreshed")).toBeInTheDocument();
    });
  });

  it("handles OAuth callback success param and displays success toast", async () => {
    // Set URL query param
    window.history.pushState({}, "Test", "/social/accounts?oauth=success&platform=instagram");

    render(<SocialAccountsView initialCompanies={mockCompanies} initialSelectedCompanyId="comp-111" />);

    await waitFor(() => {
      expect(screen.getByText("Account connected successfully")).toBeInTheDocument();
      expect(
        screen.getByText("Your INSTAGRAM channel is now connected and ready.")
      ).toBeInTheDocument();
    });
  });

  it("handles OAuth callback failure param and displays error toast", async () => {
    window.history.pushState(
      {},
      "Test",
      "/social/accounts?oauth=error&error_description=User%20denied%20access"
    );

    render(<SocialAccountsView initialCompanies={mockCompanies} initialSelectedCompanyId="comp-111" />);

    await waitFor(() => {
      expect(screen.getByText("Account connection failed")).toBeInTheDocument();
      expect(screen.getByText("User denied access")).toBeInTheDocument();
    });
  });

  it("security invariant: sensitive tokens or secrets are never rendered in the DOM", async () => {
    const { container } = render(
      <SocialAccountsView initialCompanies={mockCompanies} initialSelectedCompanyId="comp-111" />
    );

    await waitFor(() => {
      expect(screen.getByText("acme_official")).toBeInTheDocument();
    });

    const htmlContent = container.innerHTML;
    expect(htmlContent).not.toContain("access_token");
    expect(htmlContent).not.toContain("refresh_token");
    expect(htmlContent).not.toContain("client_secret");
    expect(htmlContent).not.toContain("SOCIAL_TOKEN_ENCRYPTION_KEY");
  });

  it("switching to providers tab renders all available integrations", async () => {
    render(<SocialAccountsView initialCompanies={mockCompanies} initialSelectedCompanyId="comp-111" />);

    await waitFor(() => {
      expect(screen.getByText("acme_official")).toBeInTheDocument();
    });

    const providersTab = screen.getByTestId("tab-providers");
    fireEvent.click(providersTab);

    expect(screen.getByTestId("providers-grid")).toBeInTheDocument();
    expect(screen.getByTestId("provider-card-instagram")).toBeInTheDocument();
    expect(screen.getByTestId("provider-card-facebook")).toBeInTheDocument();
    expect(screen.getByTestId("provider-card-linkedin")).toBeInTheDocument();
    expect(screen.getByTestId("provider-card-youtube")).toBeInTheDocument();
  });
});
