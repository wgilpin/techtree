# NO_AUTH Implementation Plan

## Goal

Implement an environment variable, `NO_AUTH`, that, when set:

a) Allows API calls to be made without authentication.
b) Logs the fact that `NO_AUTH` is active on every relevant API call.

## Scope

This change affects the following routers:

*   `backend/routers/lesson_router.py`
*   `backend/routers/syllabus_router.py`
*   `backend/routers/progress_router.py`

## Implementation Steps

1.  **Modify `get_current_user` function:**

    *   File: `backend/routers/auth_router.py`
    *   Add `import os` at the beginning of the file.
    *   Modify the `get_current_user` function to check for the `NO_AUTH` environment variable using `os.environ.get('NO_AUTH')`.
    *   If `NO_AUTH` is set:
        *   Log a warning message to the application logger: `logger.warning("NO_AUTH is active. Bypassing authentication.")`
        *   Return a dummy user object: `return User(user_id="no-auth", email="no-auth", name="No Auth User")`
    *   If `NO_AUTH` is not set, proceed with the existing authentication logic.

2.  **Modify Router Files:**

    *   Files: `backend/routers/lesson_router.py`, `backend/routers/syllabus_router.py`, `backend/routers/progress_router.py`
    *   Import `Response` from `fastapi`: `from fastapi import Response`
    *   In each route handler that uses the `get_current_user` dependency:
        *   Add a `response: Response` parameter to the function signature.
        *   Check if the `current_user` object exists and has a `user_id` of "no-auth": `if current_user and current_user.user_id == "no-auth":`
        *   If the condition is true, add the `X-No-Auth` header to the response: `response.headers["X-No-Auth"] = "true"`

## Mermaid Diagram

```mermaid
graph TD
    subgraph "User Request"
        A[User sends API Request] --> B{NO_AUTH set?}
    end

    subgraph "backend/routers/auth_router.py"
        B -- Yes --> C[Return Dummy User]
        B -- No --> D[Verify JWT Token]
        D -- Valid --> E[Return Authenticated User]
        D -- Invalid --> F[Return 401 Error]
    end

    subgraph "Affected Routers (lesson, syllabus, progress)"
        C --> G[Process Request]
        E --> G
        G --> H{Check user_id}
        H -- "no-auth" --> I[Add X-No-Auth Header]
        H -- Other --> J[Return Response]
        I --> J
    end

    subgraph "Logging"
        C --> K[Log "NO_AUTH active"]
    end
```

## Logging

The message "NO_AUTH is active. Bypassing authentication." will be logged to the existing application logger whenever an API call is made with the `NO_AUTH` environment variable set.

## Response Header

The header `X-No-Auth: true` will be added to the response of any API call made to the affected routers when `NO_AUTH` is set.