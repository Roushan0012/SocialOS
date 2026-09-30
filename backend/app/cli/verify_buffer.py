"""CLI tool to verify read-only Buffer API connectivity.

Performs a strictly read-only verification of:
1. Account & Organization details (GetOrganizations)
2. Connected channels for each organization (GetChannels)

Security:
- Never outputs or logs BUFFER_API_KEY or Authorization headers.
- Does not modify, schedule, publish, or delete any resources.
"""
import asyncio
import sys
from typing import Optional

from app.core.config import settings
from app.services.buffer import (
    BufferAuthError,
    BufferClient,
    BufferConnectionError,
    BufferError,
    BufferGraphQLError,
    BufferMissingApiKeyError,
    BufferTimeoutError,
)


async def run_verification() -> int:
    """Run read-only Buffer API connectivity check.

    Returns:
        int: 0 on success or cleanly handled missing key, non-zero on failure.
    """
    if not settings.BUFFER_API_KEY or not settings.BUFFER_API_KEY.strip():
        print("[-] BUFFER_API_KEY is not set or empty in the local backend environment.")
        print("[-] Skipping live Buffer connectivity check.")
        print("[-] To run live check, add BUFFER_API_KEY=<your-key> to .env.")
        return 0

    print("[*] BUFFER_API_KEY detected. Starting read-only Buffer connectivity check...")
    client = BufferClient()

    try:
        overview = await client.verify_connectivity()
    except BufferAuthError as e:
        print(f"[!] Authentication Error: {e}")
        return 1
    except BufferGraphQLError as e:
        print(f"[!] GraphQL Error: {e}")
        return 1
    except BufferTimeoutError as e:
        print(f"[!] Timeout Error: {e}")
        return 1
    except BufferConnectionError as e:
        print(f"[!] Connection Error: {e}")
        return 1
    except BufferError as e:
        print(f"[!] Buffer API Error: {e}")
        return 1
    except Exception as e:
        print(f"[!] Unexpected error: {type(e).__name__}: {e}")
        return 1

    # Report results safely (no secrets printed)
    print("\n================ BUFFER CONNECTIVITY REPORT ================")
    print(f"Account ID:   {overview.account.id}")
    print(f"Account Name: {overview.account.name or 'N/A'}")
    print(f"Account Email: {overview.account.email or 'N/A'}")
    print(f"Total Organizations: {len(overview.account.organizations)}")

    for org_with_ch in overview.organizations_with_channels:
        org = org_with_ch.organization
        print(f"\n--- Organization: {org.name} (ID: {org.id}) ---")
        print(f"Total Channels: {len(org_with_ch.channels)}")
        for ch in org_with_ch.channels:
            paused_str = "Paused" if ch.is_queue_paused else "Active"
            print(f"  • [{ch.service.upper()}] {ch.name} (ID: {ch.id}, Queue: {paused_str})")

    print("\n============================================================")
    print("[+] Buffer API connectivity check SUCCEEDED (strictly read-only).")
    return 0


def main() -> None:
    code = asyncio.run(run_verification())
    sys.exit(code)


if __name__ == "__main__":
    main()
