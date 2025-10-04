# TableTap Console Backend API Documentation

**Base URL**: `https://ttc.onehiveafrica.com`

## Authentication

All protected endpoints require a Bearer token from Clerk:
```
Authorization: Bearer <clerk_jwt_token>
```

For tenant-specific endpoints, include the tenant domain:
```
Host: <tenant_domain>
```

---

## Public Endpoints (No Auth Required)

### Health Check
```http
GET /api/health/
```
**Response:**
```json
{
  "status": "healthy",
  "message": "TableTap Console Backend is running",
  "version": "1.0.0",
  "tenant_name": "Public",
  "schema_name": "public"
}
```

### Clerk Webhook
```http
POST /api/auth/webhook/clerk/
```
**Purpose**: Automatically creates tenants when users sign up via Clerk

---

## Authentication Endpoints

### Test Authentication
```http
POST /api/auth/test/
Authorization: Bearer <token>
```
**Response:**
```json
{
  "message": "Authentication successful!",
  "user": "user@example.com",
  "tenant": "Restaurant Name",
  "data_received": {}
}
```

### Get User Profile
```http
GET /api/auth/profile/
Authorization: Bearer <token>
```
**Response:**
```json
{
  "id": 1,
  "username": "clerk_user_id",
  "email": "user@example.com",
  "first_name": "John",
  "last_name": "Doe",
  "clerk_user_id": "user_123",
  "is_verified": true
}
```

### Get User Tenant
```http
GET /api/auth/tenant/
Authorization: Bearer <token>
```
**Response:**
```json
{
  "tenant_id": 1,
  "schema_name": "tenant_abc123",
  "name": "John's Restaurant",
  "subscription_status": "trial",
  "trial_end_date": "2025-10-02T10:00:00Z",
  "is_active": true
}
```

---

## Tenant Management (Public Schema)

### List Tenants
```http
GET /api/tenants/
Authorization: Bearer <token>
```

### Create Tenant
```http
POST /api/tenants/
Authorization: Bearer <token>
Content-Type: application/json

{
  "name": "Restaurant Name",
  "contact_email": "owner@restaurant.com",
  "business_type": "restaurant"
}
```

---

## Staff Management (Tenant Schema)

**Note**: Include tenant domain in Host header

### List Staff Members
```http
GET /api/staff/members/
Authorization: Bearer <token>
Host: <tenant_domain>
```

### Create Staff Member
```http
POST /api/staff/members/
Authorization: Bearer <token>
Host: <tenant_domain>
Content-Type: application/json

{
  "user": {
    "email": "staff@restaurant.com",
    "first_name": "Jane",
    "last_name": "Smith"
  },
  "role": 1,
  "is_active": true
}
```

### List Roles
```http
GET /api/staff/roles/
Authorization: Bearer <token>
Host: <tenant_domain>
```

### Create Role
```http
POST /api/staff/roles/
Authorization: Bearer <token>
Host: <tenant_domain>
Content-Type: application/json

{
  "name": "Manager",
  "description": "Restaurant Manager",
  "permissions": ["manage_staff", "view_analytics"]
}
```

---

## Tools & Access Control (Tenant Schema)

### List Tools
```http
GET /api/tools/
Authorization: Bearer <token>
Host: <tenant_domain>
```

### Generate SSO Token
```http
POST /api/tools/sso-token/
Authorization: Bearer <token>
Host: <tenant_domain>
Content-Type: application/json

{
  "tool_id": 1,
  "expires_in": 3600
}
```

---

## Subscriptions (Public Schema)

### List Plans
```http
GET /api/subscriptions/plans/
```
**Response:**
```json
[
  {
    "id": 3,
    "name": "Professional", 
    "plan_type": "professional",
    "description": "Complete solution for growing restaurants with POS system",
    "price_usd": 19.99,
    "price_ghs": 253.47,
    "price_ngn": 29698.50,
    "includes_digital_menu": true,
    "includes_pos": true,
    "includes_cms": false,
    "allows_menu_images": true,
    "max_menu_items": -1,
    "has_basic_analytics": true,
    "has_advanced_analytics": true,
    "support_level": "priority",
    "is_featured": true,
    "features_list": [
      "Digital Menu (Unlimited items)",
      "POS System",
      "Basic Analytics",
      "Advanced Analytics", 
      "Priority Support"
    ]
  }
]
```

### Get User Subscription
```http
GET /api/subscriptions/subscription/
Authorization: Bearer <token>
```

### Create Subscription
```http
POST /api/subscriptions/subscription/create/
Authorization: Bearer <token>
Content-Type: application/json

{
  "plan_id": 1,
  "currency": "USD"
}
```

### Initialize Payment
```http
POST /api/subscriptions/payment/initialize/
Authorization: Bearer <token>
Content-Type: application/json

{
  "subscription_id": 1,
  "currency": "USD",
  "callback_url": "https://yourapp.com/payment/success"
}
```

### Get Payment History
```http
GET /api/subscriptions/payment/history/
Authorization: Bearer <token>
```

---

## Analytics (Tenant Schema)

### Track Event
```http
POST /api/analytics/events/
Authorization: Bearer <token>
Host: <tenant_domain>
Content-Type: application/json

{
  "event_type": "order_created",
  "data": {
    "order_id": "123",
    "amount": 25.50
  }
}
```

### Get Dashboard Metrics
```http
GET /api/analytics/dashboard/
Authorization: Bearer <token>
Host: <tenant_domain>
```

---

## Error Responses

### 401 Unauthorized
```json
{
  "detail": "Authentication credentials were not provided."
}
```

### 403 Forbidden
```json
{
  "detail": "You do not have permission to perform this action."
}
```

### 404 Not Found
```json
{
  "detail": "Not found."
}
```

---

## Multi-Tenant Architecture

- **Public Schema**: Tenant management, authentication, subscriptions
- **Tenant Schemas**: Staff, tools, analytics (restaurant-specific data)
- **Domain Routing**: Each tenant gets isolated data via Host header
- **Automatic Tenant Creation**: New tenants created via Clerk webhook

## Frontend Integration

```javascript
// API Client Example
const apiCall = async (endpoint, options = {}) => {
  const token = await getToken(); // From Clerk
  
  return fetch(`https://ttc.onehiveafrica.com${endpoint}`, {
    ...options,
    headers: {
      'Authorization': `Bearer ${token}`,
      'Content-Type': 'application/json',
      ...options.headers,
    },
  });
};

// Tenant-specific call
const tenantApiCall = async (endpoint, tenantDomain, options = {}) => {
  const token = await getToken();
  
  return fetch(`https://ttc.onehiveafrica.com${endpoint}`, {
    ...options,
    headers: {
      'Authorization': `Bearer ${token}`,
      'Host': tenantDomain,
      'Content-Type': 'application/json',
      ...options.headers,
    },
  });
};
```
