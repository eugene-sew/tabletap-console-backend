# TableTap Console Backend

The central management system for TableTap - a multi-tenant Django backend that manages restaurants, staff, subscriptions, and tool access across the TableTap ecosystem.

## Features

- **Multi-tenant Architecture**: Schema-based isolation using django-tenant-schemas
- **Clerk Integration**: Authentication and user management
- **Paystack Integration**: Subscription billing and payments
- **Tool Access Management**: SSO tokens for POS, Menu, and CMS tools
- **Analytics**: Event tracking and dashboard metrics
- **Staff Management**: Role-based permissions and access control

## Tech Stack

- Django 4.2 + Django REST Framework
- PostgreSQL with multi-tenancy
- Redis for caching and Celery
- Clerk for authentication
- Paystack for payments
- Docker for containerization

## Frontend Integration

This backend is designed to work with the **tabletap-console** React frontend. The backend runs on port **3001** to match the frontend's API expectations.

### Quick Integration Test

```bash
# Test backend-frontend compatibility
python test_integration.py
```

## Quick Start

### 1. Clone and Setup

```bash
cd tabletap-console-backend
cp .env.example .env
# Edit .env with your configuration
```

### 2. Start with Docker

```bash
docker-compose up -d
```

### 3. Run Migrations

```bash
docker-compose exec web python manage.py migrate_schemas --shared
docker-compose exec web python manage.py migrate_schemas
```

### 4. Create Superuser

```bash
docker-compose exec web python manage.py createsuperuser
```

### 5. Setup Initial Data

```bash
docker-compose exec web python manage.py setup_initial_data
```

### 6. Test Integration

```bash
# Install requests if not available
pip install requests

# Run integration test
python test_integration.py
```

## Frontend Setup

The backend is configured to work with the React frontend at `http://localhost:3000`:

1. **CORS**: Configured for `localhost:3000`
2. **API Port**: Backend runs on port `3001` (mapped from internal `8000`)
3. **Authentication**: Compatible with Clerk JWT tokens
4. **API Base URL**: `http://localhost:3001/api`

### Frontend Environment Variables

Make sure your frontend `.env.local` includes:

```bash
VITE_API_BASE_URL=http://localhost:3001/api
VITE_CLERK_PUBLISHABLE_KEY=your-clerk-publishable-key
```

## API Endpoints

### Health Check
- `GET /api/health/` - Backend health status

### Authentication
- `POST /api/auth/webhook/clerk/` - Clerk webhook for user events
- `GET /api/auth/profile/` - Get current user profile

### Tenants
- `GET /api/tenants/` - List tenants
- `POST /api/tenants/` - Create tenant
- `POST /api/tenants/{id}/activate_subscription/` - Activate subscription
- `POST /api/tenants/{id}/deactivate_subscription/` - Deactivate subscription

### Staff
- `GET /api/staff/roles/` - List roles
- `GET /api/staff/members/` - List staff members
- `POST /api/staff/members/` - Add staff member
- `POST /api/staff/members/{id}/activate/` - Activate staff
- `POST /api/staff/members/{id}/deactivate/` - Deactivate staff

### Subscriptions
- `GET /api/subscriptions/plans/` - List subscription plans
- `GET /api/subscriptions/subscriptions/` - List subscriptions
- `POST /api/subscriptions/subscribe/` - Subscribe to plan
- `POST /api/subscriptions/webhook/paystack/` - Paystack webhook

### Tools
- `GET /api/tools/available/` - List available tools
- `GET /api/tools/access/` - List user's tool access
- `POST /api/tools/sso/generate/` - Generate SSO token
- `POST /api/tools/sso/verify/` - Verify SSO token

### Analytics
- `GET /api/analytics/events/` - List events
- `POST /api/analytics/track/` - Track event
- `GET /api/analytics/dashboard/` - Dashboard summary

## Configuration

### Environment Variables

```bash
# Django
SECRET_KEY=your-secret-key
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1

# Database
DB_NAME=tabletap_console
DB_USER=postgres
DB_PASSWORD=mysecretpassword
DB_HOST=localhost
DB_PORT=5434

# Redis
REDIS_URL=redis://localhost:6379/0

# Clerk
CLERK_SECRET_KEY=your-clerk-secret-key
CLERK_PUBLISHABLE_KEY=your-clerk-publishable-key

# Paystack
PAYSTACK_SECRET_KEY=your-paystack-secret-key
PAYSTACK_PUBLIC_KEY=your-paystack-public-key
```

### Clerk Webhook Setup

1. In your Clerk dashboard, add a webhook endpoint: `https://your-domain.com/api/auth/webhook/clerk/`
2. Subscribe to `user.created` events
3. The webhook will automatically create tenants for new users

### Paystack Webhook Setup

1. In your Paystack dashboard, add a webhook endpoint: `https://your-domain.com/api/subscriptions/webhook/paystack/`
2. Subscribe to `charge.success` events

## Multi-Tenancy

Each restaurant gets its own PostgreSQL schema. The system uses:

- **Shared Apps**: Tenants, Authentication, Subscriptions, Analytics
- **Tenant Apps**: Staff, Tools (isolated per tenant)

### Creating a New Tenant

```python
from tenants.models import Tenant, Domain

tenant = Tenant.objects.create(
    schema_name='restaurant_abc',
    name='ABC Restaurant',
    contact_email='admin@abc-restaurant.com'
)

Domain.objects.create(
    domain='abc.tabletap.com',
    tenant=tenant,
    is_primary=True
)
```

## SSO Token Flow

1. User requests access to a tool (POS/Menu/CMS)
2. Console generates JWT token with tenant info
3. Tool receives token and verifies with Console
4. Tool grants access based on verification

```python
# Generate token
POST /api/tools/sso/generate/
{
    "tool_id": 1
}

# Verify token (from tool)
POST /api/tools/sso/verify/
{
    "token": "jwt-token-here"
}
```

## Development

### Running Tests

```bash
docker-compose exec web python manage.py test
```

### Adding New Apps

1. Create app in appropriate category (shared/tenant)
2. Add to `SHARED_APPS` or `TENANT_APPS` in settings
3. Run migrations: `python manage.py migrate_schemas`

### Database Migrations

```bash
# Shared schema migrations
python manage.py migrate_schemas --shared

# Tenant schema migrations
python manage.py migrate_schemas

# Create new migration
python manage.py makemigrations app_name
```

## Production Deployment

1. Set `DEBUG=False`
2. Configure proper `ALLOWED_HOSTS`
3. Use environment variables for secrets
4. Setup SSL/TLS certificates
5. Configure proper CORS origins
6. Use production database and Redis
7. Setup monitoring and logging

## Troubleshooting

### Common Issues

1. **CORS Errors**: Check `CORS_ALLOWED_ORIGINS` in settings
2. **Database Connection**: Verify PostgreSQL is running on port 5434
3. **Redis Connection**: Ensure Redis is accessible
4. **Clerk Authentication**: Check JWT token format and Clerk configuration
5. **Port Conflicts**: Backend should run on port 3001 for frontend compatibility

### Integration Test Failures

Run the integration test to diagnose issues:

```bash
python test_integration.py
```

This will check:
- Backend health and connectivity
- CORS configuration
- API endpoint accessibility

## Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Frontend      │    │   POS Tool      │    │   Menu Tool     │
│   (React)       │    │                 │    │                 │
│   Port: 3000    │    │                 │    │                 │
└─────────┬───────┘    └─────────┬───────┘    └─────────┬───────┘
          │                      │                      │
          │              SSO Token Exchange             │
          │                      │                      │
          └──────────────────────┼──────────────────────┘
                                 │
                    ┌─────────────┴───────────┐
                    │   Console Backend       │
                    │   (Django + DRF)        │
                    │   Port: 3001            │
                    │                         │
                    │  ┌─────────────────┐    │
                    │  │   PostgreSQL    │    │
                    │  │   (Multi-tenant)│    │
                    │  │   Port: 5434    │    │
                    │  └─────────────────┘    │
                    │                         │
                    │  ┌─────────────────┐    │
                    │  │     Redis       │    │
                    │  │   (Cache/Queue) │    │
                    │  │   Port: 6379    │    │
                    │  └─────────────────┘    │
                    └─────────────────────────┘
                                 │
                    ┌─────────────┴───────────┐
                    │   External Services     │
                    │                         │
                    │  ┌─────────┐ ┌────────┐ │
                    │  │  Clerk  │ │Paystack│ │
                    │  └─────────┘ └────────┘ │
                    └─────────────────────────┘
```

## License

MIT License
