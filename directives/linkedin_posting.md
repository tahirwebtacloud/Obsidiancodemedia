# SOP: LinkedIn OAuth & Direct Posting Integration

## Goal

Enable the application to authenticate users via LinkedIn OAuth 2.0 and programmatically create posts (text, image, article) on their behalf using the LinkedIn RestLi 2.0 API.

## Workflow Overview

### 1. Authentication (OAuth 2.0)

- **Method**: 3-Legged Authorization Code Flow.
- **Scopes**: `w_member_social`, `openid`, `profile`, `email`.
- **Redirect URI**: `http://localhost:9999/auth/linkedin/callback`.
- **Logic**:
    1. Redirect user to LinkedIn Auth URL.
    2. Handle callback to retrieve `code`.
    3. Exchange `code` for `access_token` and `refresh_token`.
    4. Store tokens securely (encrypted or restricted access).

### 2. Member Discovery

- **Endpoint**: `GET https://api.linkedin.com/v2/userinfo`.
- **Purpose**: Retrieve the member's Person URN (`urn:li:person:XXXX`) required for the `author` field in post requests.

### 3. Creating a Text Post

- **Endpoint**: `POST https://api.linkedin.com/rest/posts`.
- **Payload**:

```json
{
  "author": "urn:li:person:XXXX",
  "commentary": "Your post content here",
  "visibility": "PUBLIC",
  "lifecycleState": "PUBLISHED"
}
```

### 4. Creating an Image Post

1. **Initialize**: `POST /v2/assets?action=registerUpload`.
2. **Upload**: Use the `uploadUrl` from step 1 to `PUT` the binary image data.
3. **Finish**: Create post using the asset URN in `content.media.id`.

### 5. Sharing Articles/Links

- **Payload**: Same as Text Post, but include `content` object with `article` URL and metadata.

## Tools & Scripts (Layer 3)

- `execution/linkedin_auth.py`: Handles token exchange and refreshing.
- `execution/linkedin_poster.py`: Handles payload construction and API calls for different post types.

## Error Handling

- **429 Rate Limit**: Detect and log "LinkedIn: Rate limit reached. Retrying in X seconds."
- **401 Unauthorized**: Trigger token refresh logic or notify user to re-link account.

> [!NOTE]
> **Polls**: Programmatic poll creation is restricted to LinkedIn Marketing Partners. This feature will be skipped unless partner status is achieved.
