# Restaurant Management SaaS — Backend

A production-ready, multi-tenant restaurant management platform built with Django REST Framework and PostgreSQL.

---

## Architecture

```
abhilash-restaurant-saas/
├── core/                        # Django project (settings, urls, wsgi, asgi)
│   └── settings/
│       ├── base.py              # Shared settings (all environments)
│       ├── development.py       # Development overrides
│       └── production.py        # Production overrides + security headers
├── apps/
│   ├── authentication/          # JWT login/logout/register, password reset
│   ├── users/                   # Custom User model + RBAC roles
│   ├── restaurants/             # Tenant model (Restaurant) + settings
│   ├── menu/                    # Categories, MenuItems, Variants
│   ├── orders/                  # Tables, Orders, OrderItems, status machine
│   └── kitchen/                 # KitchenTickets, Stations, display board
├── common/                      # Shared utilities
│   ├── models.py                # Abstract base models (UUID, timestamps, TenantAware)
│   ├── permissions.py           # RBAC permission classes
│   ├── mixins.py                # TenantQuerysetMixin for automatic row isolation
│   ├── middleware.py            # TenantMiddleware (attaches request.tenant)
│   ├── pagination.py            # Standardised paginated responses
│   └── exceptions.py           # Unified error envelope
└── logs/                        # Log files (gitignored)
```

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Framework | Django 4.2 + Django REST Framework |
| Auth | JWT (djangorestframework-simplejwt) |
| Database | PostgreSQL (psycopg2 + dj-database-url) |
| Cache | Redis (django-redis) |
| Task Queue | Celery + Redis |
| WebSocket | Django Channels + Redis (scaffolded, ready to implement) |
| API Docs | drf-spectacular (Swagger + ReDoc) |
| Storage | Local (dev) / AWS S3 (prod) |
| Server | Gunicorn + WhiteNoise |

---

## Multi-Tenancy

- **Strategy**: Shared database, shared schema, `restaurant` FK on every tenant-scoped model.
- `TenantBaseModel` (in `common/models.py`) adds `restaurant` FK + UUID PK + timestamps to any model.
- `TenantMiddleware` attaches `request.tenant` on every request.
- `TenantQuerysetMixin` automatically filters querysets to the current tenant in all views.
- Super-admins bypass tenant filtering and can see all data across tenants.

---

## RBAC Roles

| Role | Capabilities |
|------|-------------|
| `super_admin` | Manage all tenants, unrestricted access |
| `owner` | Full restaurant configuration, staff management |
| `manager` | Menu, orders, staff, reports |
| `chef` | View and update kitchen tickets |
| `waiter` | Create and manage orders |
| `cashier` | Manage payments and order completion |

Permission classes live in `common/permissions.py`.

---

## API Endpoints

| Method | URL | Description |
|--------|-----|-------------|
| POST | `/api/v1/auth/register/` | Register new restaurant owner |
| POST | `/api/v1/auth/login/` | Obtain JWT token pair |
| POST | `/api/v1/auth/logout/` | Blacklist refresh token |
| POST | `/api/v1/auth/token/refresh/` | Refresh access token |
| POST | `/api/v1/auth/forgot-password/` | Request password reset |
| POST | `/api/v1/auth/reset-password/` | Complete password reset |
| GET/PUT | `/api/v1/users/me/` | Current user profile |
| POST | `/api/v1/users/me/change-password/` | Change password |
| GET/POST | `/api/v1/users/` | List / create staff |
| GET/PUT/DELETE | `/api/v1/users/{id}/` | Staff detail |
| GET | `/api/v1/restaurants/` | List all restaurants (super-admin) |
| GET/PUT | `/api/v1/restaurants/me/` | Current restaurant profile |
| GET/PUT | `/api/v1/restaurants/me/settings/` | Restaurant feature flags |
| GET/POST | `/api/v1/menu/categories/` | Menu categories |
| GET/PUT/DELETE | `/api/v1/menu/categories/{id}/` | Category detail |
| GET/POST | `/api/v1/menu/items/` | Menu items |
| GET/PUT/DELETE | `/api/v1/menu/items/{id}/` | Item detail |
| GET/POST | `/api/v1/menu/items/{id}/variants/` | Item variants |
| GET/POST | `/api/v1/orders/tables/` | Tables |
| GET/POST | `/api/v1/orders/` | Create / list orders |
| GET | `/api/v1/orders/{id}/` | Order detail |
| PATCH | `/api/v1/orders/{id}/status/` | Update order status |
| GET/POST | `/api/v1/kitchen/stations/` | Kitchen stations |
| GET | `/api/v1/kitchen/tickets/` | Kitchen display board |
| GET | `/api/v1/kitchen/tickets/{id}/` | Ticket detail |
| PATCH | `/api/v1/kitchen/tickets/{id}/status/` | Update ticket status |
| GET | `/api/v1/docs/` | Swagger UI |
| GET | `/api/v1/redoc/` | ReDoc |

---

## Order Status Machine

```
PENDING → CONFIRMED → PREPARING → READY → SERVED → COMPLETED
    ↓           ↓
CANCELLED   CANCELLED
```

Kitchen ticket: `PENDING → IN_PROGRESS → READY → DELIVERED`.

---

## Quick Start

```bash
# 1. Clone and create a virtual environment
git clone <repo-url>
cd abhilash-restaurant-saas
python -m venv .venv && source .venv/bin/activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Configure environment
cp .env.example .env
# Set SECRET_KEY and DATABASE_URL in .env

# 4. Set DATABASE_URL — choose one:

#   Local PostgreSQL:
#   DATABASE_URL=postgresql://postgres:password@localhost:5432/restaurant_saas_db
#   (create the DB first: createdb restaurant_saas_db)

#   Cloud PostgreSQL (Neon, Supabase, Railway, Render):
#   DATABASE_URL=postgresql://user:password@host/dbname?sslmode=require
#   (copy the connection string directly from your provider's dashboard)

# 5. Run migrations
python manage.py migrate

# 6. Create a superuser
python manage.py createsuperuser

# 7. Start the development server
python manage.py runserver
```

### Run Tests

```bash
pytest
pytest --cov=apps --cov=common --cov-report=html   # with coverage
```

### Start Celery (optional)

```bash
celery -A core worker --loglevel=info
celery -A core beat --loglevel=info
```

---

## WebSocket (Future)

The project ships with Django Channels and `core/asgi.py` pre-configured. To add real-time kitchen display or live order updates:

1. Create `consumers.py` in `apps/kitchen/` or `apps/orders/`
2. Define routing in a `routing.py` file in the same app
3. Uncomment the import lines in `core/asgi.py`

---

## Production Deployment

```bash
DJANGO_ENV=production
python manage.py collectstatic --noinput
gunicorn core.asgi:application -k uvicorn.workers.UvicornWorker
```
