# TableTap Console - Authentication Integration Guide

## Frontend Integration with Clerk JWT

### 1. API Client Setup

```javascript
// utils/api.js
import { useAuth } from "@clerk/nextjs";

const API_BASE_URL = "https://ttc.onehiveafrica.com";

export const useApiClient = () => {
  const { getToken } = useAuth();

  const apiCall = async (endpoint, options = {}) => {
    const token = await getToken();

    const response = await fetch(`${API_BASE_URL}${endpoint}`, {
      ...options,
      headers: {
        Authorization: `Bearer ${token}`,
        "Content-Type": "application/json",
        ...options.headers,
      },
    });

    if (!response.ok) {
      throw new Error(`API Error: ${response.status}`);
    }

    return response.json();
  };

  return { apiCall };
};
```

### 2. Test Authentication

```javascript
// Test component
import { useApiClient } from "../utils/api";

export const AuthTest = () => {
  const { apiCall } = useApiClient();

  const testAuth = async () => {
    try {
      const result = await apiCall("/api/auth/test/", {
        method: "POST",
        body: JSON.stringify({ test: "data" }),
      });
      console.log("Auth test result:", result);
    } catch (error) {
      console.error("Auth test failed:", error);
    }
  };

  return <button onClick={testAuth}>Test Authentication</button>;
};
```

### 3. Get User Profile

```javascript
const getUserProfile = async () => {
  const profile = await apiCall("/api/auth/profile/");
  return profile;
};
```

### 4. Get User Tenant

```javascript
const getUserTenant = async () => {
  const tenant = await apiCall("/api/auth/tenant/");
  return tenant;
};
```

### 5. Tenant-Aware API Calls

For tenant-specific endpoints, you need to include the tenant domain:

```javascript
const callTenantAPI = async (endpoint, tenantDomain) => {
  const token = await getToken();

  const response = await fetch(`${API_BASE_URL}${endpoint}`, {
    headers: {
      Authorization: `Bearer ${token}`,
      Host: tenantDomain, // Important for tenant routing
      "Content-Type": "application/json",
    },
  });

  return response.json();
};

// Example: Get staff members for a specific tenant
const getStaffMembers = async (tenantDomain) => {
  return callTenantAPI("/api/staff/members/", tenantDomain);
};
```

## Test Endpoints

1. **Test Auth**: `POST /api/auth/test/` - Verify JWT authentication
2. **User Profile**: `GET /api/auth/profile/` - Get current user info
3. **User Tenant**: `GET /api/auth/tenant/` - Get user's tenant info
4. **Health Check**: `GET /api/health/` - Check API status

## Authentication Flow

1. User signs up/logs in via Clerk
2. Clerk webhook creates tenant automatically
3. Frontend gets JWT token from Clerk
4. Include JWT in API requests as `Bearer` token
5. Backend verifies JWT and identifies user
6. For tenant-specific operations, include tenant domain in Host header

## Error Handling

```javascript
const handleApiError = (error) => {
  if (error.message.includes("401")) {
    // Redirect to login
    window.location.href = "/sign-in";
  } else if (error.message.includes("403")) {
    // Show permission denied message
    console.error("Permission denied");
  } else {
    // Handle other errors
    console.error("API Error:", error);
  }
};
```
