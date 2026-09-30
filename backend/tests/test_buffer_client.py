"""Focused Test Suite for Buffer GraphQL API Integration.

Covers:
1. Successful account + organization retrieval (GetOrganizations)
2. Successful channel retrieval (GetChannels)
3. Full read-only connectivity check (verify_connectivity)
4. Missing / unconfigured API key handling
5. HTTP 401 authentication failure (distinguished from other errors)
6. HTTP 403 forbidden error handling
7. HTTP 500 / other status error handling
8. GraphQL error handling (200 OK with errors payload)
9. GraphQL authentication error handling
10. Timeout error handling
11. Network connection error handling
12. Strict security verification: Secret NEVER present in logs, exceptions, or client string representation
13. Settings integration verification for BUFFER_API_KEY
"""
import json
import logging
from typing import Any, Dict
import pytest
import httpx

from app.core.config import Settings
from app.services.buffer import (
    BufferAccount,
    BufferAccountOverview,
    BufferAPIError,
    BufferAuthError,
    BufferChannel,
    BufferClient,
    BufferConnectionError,
    BufferError,
    BufferGraphQLError,
    BufferMissingApiKeyError,
    BufferOrganization,
    BufferTimeoutError,
)

MOCK_ORGS_PAYLOAD = {
    "data": {
        "account": {
            "id": "acc_buf_12345",
            "name": "SocialOS Test User",
            "email": "test@socialos.local",
            "organizations": [
                {
                    "id": "org_buf_67890",
                    "name": "SocialOS Workspace",
                }
            ],
        }
    }
}

MOCK_CHANNELS_PAYLOAD = {
    "data": {
        "channels": [
            {
                "id": "ch_insta_1106",
                "name": "roushan_1106",
                "service": "instagram",
                "avatar": "https://buffer-static.com/insta.jpg",
                "isQueuePaused": False,
            },
            {
                "id": "ch_fb_test",
                "name": "Socialos Test",
                "service": "facebook",
                "avatar": "https://buffer-static.com/fb.jpg",
                "isQueuePaused": False,
            },
        ]
    }
}


@pytest.fixture
def dummy_secret() -> str:
    return "buf-test-personal-token-xyz-987654321"


@pytest.mark.asyncio
async def test_get_organizations_success(dummy_secret: str):
    """Test successful retrieval and parsing of Buffer account and organizations."""
    captured_auth_header = None

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal captured_auth_header
        captured_auth_header = request.headers.get("Authorization")
        req_body = json.loads(request.content.decode("utf-8"))
        assert "GetOrganizations" in req_body.get("query", "")
        return httpx.Response(200, json=MOCK_ORGS_PAYLOAD)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as mock_http:
        client = BufferClient(api_key=dummy_secret, http_client=mock_http)
        account = await client.get_account_and_organizations()

    assert captured_auth_header == f"Bearer {dummy_secret}"
    assert isinstance(account, BufferAccount)
    assert account.id == "acc_buf_12345"
    assert account.name == "SocialOS Test User"
    assert account.email == "test@socialos.local"
    assert len(account.organizations) == 1
    assert account.organizations[0].id == "org_buf_67890"
    assert account.organizations[0].name == "SocialOS Workspace"


@pytest.mark.asyncio
async def test_get_channels_success(dummy_secret: str):
    """Test successful retrieval and parsing of connected social channels."""
    captured_variables = None

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal captured_variables
        req_body = json.loads(request.content.decode("utf-8"))
        captured_variables = req_body.get("variables")
        query_str = req_body.get("query", "")
        assert "GetChannels" in query_str
        assert "$organizationId: OrganizationId!" in query_str
        return httpx.Response(200, json=MOCK_CHANNELS_PAYLOAD)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as mock_http:
        client = BufferClient(api_key=dummy_secret, http_client=mock_http)
        channels = await client.get_channels(organization_id="org_buf_67890")

    assert captured_variables == {"organizationId": "org_buf_67890"}
    assert len(channels) == 2

    # Verify Instagram channel
    ch_insta = channels[0]
    assert isinstance(ch_insta, BufferChannel)
    assert ch_insta.id == "ch_insta_1106"
    assert ch_insta.name == "roushan_1106"
    assert ch_insta.service == "instagram"
    assert ch_insta.avatar == "https://buffer-static.com/insta.jpg"
    assert ch_insta.is_queue_paused is False

    # Verify Facebook channel
    ch_fb = channels[1]
    assert isinstance(ch_fb, BufferChannel)
    assert ch_fb.id == "ch_fb_test"
    assert ch_fb.name == "Socialos Test"
    assert ch_fb.service == "facebook"
    assert ch_fb.avatar == "https://buffer-static.com/fb.jpg"
    assert ch_fb.is_queue_paused is False


@pytest.mark.asyncio
async def test_verify_connectivity_flow(dummy_secret: str):
    """Test the full read-only connectivity check querying orgs and channels."""
    def handler(request: httpx.Request) -> httpx.Response:
        req_body = json.loads(request.content.decode("utf-8"))
        query = req_body.get("query", "")
        if "GetOrganizations" in query:
            return httpx.Response(200, json=MOCK_ORGS_PAYLOAD)
        elif "GetChannels" in query:
            return httpx.Response(200, json=MOCK_CHANNELS_PAYLOAD)
        return httpx.Response(400, text="Unexpected query")

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as mock_http:
        client = BufferClient(api_key=dummy_secret, http_client=mock_http)
        overview = await client.verify_connectivity()

    assert isinstance(overview, BufferAccountOverview)
    assert overview.account.id == "acc_buf_12345"
    assert len(overview.organizations_with_channels) == 1

    org_summary = overview.organizations_with_channels[0]
    assert org_summary.organization.name == "SocialOS Workspace"
    channel_names = [ch.name for ch in org_summary.channels]
    assert "roushan_1106" in channel_names
    assert "Socialos Test" in channel_names


@pytest.mark.asyncio
async def test_missing_api_key_raises_error(monkeypatch: pytest.MonkeyPatch):
    """Verify that empty or None API key raises BufferMissingApiKeyError without HTTP call."""
    monkeypatch.setattr("app.services.buffer.client.settings.BUFFER_API_KEY", None)
    for bad_key in [None, "", "   "]:
        client = BufferClient(api_key=bad_key)
        assert client.is_configured is False
        with pytest.raises(BufferMissingApiKeyError) as exc_info:
            await client.get_account_and_organizations()
        assert "BUFFER_API_KEY is not configured" in str(exc_info.value)



@pytest.mark.asyncio
async def test_invalid_api_key_401_unauthorized(dummy_secret: str):
    """Verify HTTP 401 returns BufferAuthError distinct from other errors."""
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"message": "Invalid personal access token"})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as mock_http:
        client = BufferClient(api_key=dummy_secret, http_client=mock_http)
        with pytest.raises(BufferAuthError) as exc_info:
            await client.get_account_and_organizations()

    assert exc_info.value.status_code == 401
    assert "HTTP 401" in str(exc_info.value)
    # Ensure error is an instance of BufferAuthError and BufferError
    assert isinstance(exc_info.value, BufferAuthError)
    assert isinstance(exc_info.value, BufferError)


@pytest.mark.asyncio
async def test_forbidden_403(dummy_secret: str):
    """Verify HTTP 403 returns BufferAuthError with status 403."""
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(403, json={"message": "Forbidden"})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as mock_http:
        client = BufferClient(api_key=dummy_secret, http_client=mock_http)
        with pytest.raises(BufferAuthError) as exc_info:
            await client.get_account_and_organizations()

    assert exc_info.value.status_code == 403
    assert "HTTP 403" in str(exc_info.value)


@pytest.mark.asyncio
async def test_http_500_server_error(dummy_secret: str):
    """Verify non-401 HTTP errors raise BufferAPIError."""
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="Internal Server Error")

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as mock_http:
        client = BufferClient(api_key=dummy_secret, http_client=mock_http)
        with pytest.raises(BufferAPIError) as exc_info:
            await client.get_account_and_organizations()

    assert exc_info.value.status_code == 500
    assert "HTTP 500" in str(exc_info.value)
    assert not isinstance(exc_info.value, BufferAuthError)


@pytest.mark.asyncio
async def test_graphql_error(dummy_secret: str):
    """Verify GraphQL errors in 200 OK response raise BufferGraphQLError."""
    error_payload = {
        "errors": [
            {
                "message": "Cannot query field 'nonExistentField' on type 'Account'.",
                "locations": [{"line": 3, "column": 5}],
            }
        ]
    }

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=error_payload)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as mock_http:
        client = BufferClient(api_key=dummy_secret, http_client=mock_http)
        with pytest.raises(BufferGraphQLError) as exc_info:
            await client.get_account_and_organizations()

    assert "Cannot query field" in str(exc_info.value)
    assert len(exc_info.value.errors) == 1


@pytest.mark.asyncio
async def test_graphql_auth_error(dummy_secret: str):
    """Verify GraphQL errors describing auth failure map to BufferAuthError."""
    auth_error_payload = {
        "errors": [
            {
                "message": "Unauthorized: Invalid access token supplied",
            }
        ]
    }

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=auth_error_payload)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as mock_http:
        client = BufferClient(api_key=dummy_secret, http_client=mock_http)
        with pytest.raises(BufferAuthError) as exc_info:
            await client.get_account_and_organizations()

    assert "Unauthorized" in str(exc_info.value)
    assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_timeout_error_handling(dummy_secret: str):
    """Verify httpx.TimeoutException maps to BufferTimeoutError."""
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("Read timed out")

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as mock_http:
        client = BufferClient(api_key=dummy_secret, http_client=mock_http, timeout=5.0)
        with pytest.raises(BufferTimeoutError) as exc_info:
            await client.get_account_and_organizations()

    assert "timed out after 5.0s" in str(exc_info.value)


@pytest.mark.asyncio
async def test_connection_error_handling(dummy_secret: str):
    """Verify network connection failures map to BufferConnectionError."""
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("Connection refused")

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as mock_http:
        client = BufferClient(api_key=dummy_secret, http_client=mock_http)
        with pytest.raises(BufferConnectionError) as exc_info:
            await client.get_account_and_organizations()

    assert "Buffer API connection failed" in str(exc_info.value)


@pytest.mark.asyncio
async def test_secret_is_never_leaked_in_logs_or_exceptions(
    dummy_secret: str, caplog: pytest.LogCaptureFixture
):
    """CRITICAL SECURITY TEST: Ensure BUFFER_API_KEY is never in logs, repr, or exception text."""
    caplog.set_level(logging.DEBUG)

    # 1. Check repr and str
    client = BufferClient(api_key=dummy_secret)
    assert dummy_secret not in repr(client)
    assert dummy_secret not in str(client)
    assert dummy_secret not in f"{client}"

    # 2. Check 401 error
    def handler_401(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"error": "unauthorized"})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler_401)) as mock_http:
        c1 = BufferClient(api_key=dummy_secret, http_client=mock_http)
        try:
            await c1.get_account_and_organizations()
        except Exception as e:
            assert dummy_secret not in str(e)
            assert dummy_secret not in repr(e)

    # 3. Check 500 error
    def handler_500(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="Internal Server Error")

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler_500)) as mock_http:
        c2 = BufferClient(api_key=dummy_secret, http_client=mock_http)
        try:
            await c2.get_account_and_organizations()
        except Exception as e:
            assert dummy_secret not in str(e)
            assert dummy_secret not in repr(e)

    # 4. Check timeout error
    def handler_timeout(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("Timed out")

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler_timeout)) as mock_http:
        c3 = BufferClient(api_key=dummy_secret, http_client=mock_http)
        try:
            await c3.get_account_and_organizations()
        except Exception as e:
            assert dummy_secret not in str(e)
            assert dummy_secret not in repr(e)

    # 5. Check GraphQL error
    def handler_gql(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"errors": [{"message": "Invalid field"}]})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler_gql)) as mock_http:
        c4 = BufferClient(api_key=dummy_secret, http_client=mock_http)
        try:
            await c4.get_account_and_organizations()
        except Exception as e:
            assert dummy_secret not in str(e)
            assert dummy_secret not in repr(e)

    # 6. Verify entire captured log stream
    full_log_text = caplog.text
    assert dummy_secret not in full_log_text
    assert "Authorization" not in full_log_text


def test_config_buffer_api_key_setting():
    """Verify BUFFER_API_KEY and BUFFER_API_URL are supported in Settings."""
    custom_settings = Settings(
        BUFFER_API_KEY="test_key_abc",
        BUFFER_API_URL="https://test.buffer.local",
    )
    assert custom_settings.BUFFER_API_KEY == "test_key_abc"
    assert custom_settings.BUFFER_API_URL == "https://test.buffer.local"


@pytest.mark.asyncio
async def test_get_channels_empty_org_id_validation(dummy_secret: str):
    """Verify get_channels validates organization_id."""
    client = BufferClient(api_key=dummy_secret)
    with pytest.raises(ValueError):
        await client.get_channels("")
    with pytest.raises(ValueError):
        await client.get_channels("   ")


def test_get_channels_query_uses_organization_id_type():
    """Verify GetChannels query strictly declares $organizationId as OrganizationId! scalar."""
    from app.services.buffer.client import GET_CHANNELS_QUERY

    assert "$organizationId: OrganizationId!" in GET_CHANNELS_QUERY
    assert "$organizationId: ID!" not in GET_CHANNELS_QUERY


def test_create_post_mutation_query_structure():
    """Verify CreatePost mutation declares $input: CreatePostInput! and selects payload union."""
    from app.services.buffer.client import CREATE_POST_MUTATION

    assert "$input: CreatePostInput!" in CREATE_POST_MUTATION
    assert "createPost(input: $input)" in CREATE_POST_MUTATION
    assert "... on PostActionSuccess" in CREATE_POST_MUTATION
    assert "... on InvalidInputError" in CREATE_POST_MUTATION


@pytest.mark.asyncio
async def test_create_post_client_success(dummy_secret: str):
    """Verify BufferClient.create_post executes query and extracts createPost data."""
    mock_payload = {
        "data": {
            "createPost": {
                "__typename": "PostActionSuccess",
                "post": {"id": "post_123", "status": "buffer", "sharedNow": True},
            }
        }
    }

    mock_transport = httpx.MockTransport(
        lambda request: httpx.Response(200, json=mock_payload)
    )
    async with httpx.AsyncClient(transport=mock_transport) as http_client:
        client = BufferClient(api_key=dummy_secret, http_client=http_client)
        result = await client.create_post({"channelId": "ch_1", "mode": "shareNow"})
        assert result["__typename"] == "PostActionSuccess"
        assert result["post"]["id"] == "post_123"

