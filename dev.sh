#!/bin/bash

# TableTap Console – Development Script
# Usage:
#   ./dev.sh            → Docker Compose (original behaviour)
#   ./dev.sh --local    → Native local setup (no Docker)

set -e

MODE="docker"
if [[ "$1" == "--local" ]]; then
  MODE="local"
fi

# ─────────────────────────────────────────────────────────────────────────────
#  DOCKER MODE  (original behaviour)
# ─────────────────────────────────────────────────────────────────────────────
if [[ "$MODE" == "docker" ]]; then
  echo "Starting TableTap Backend via Docker Compose..."
  echo "  PostgreSQL : localhost:5435"
  echo "  Redis      : localhost:6379"
  echo "  Django API : localhost:3001"
  echo ""

  docker-compose -f docker-compose.dev.yml build
  docker-compose -f docker-compose.dev.yml up

  cleanup() {
    echo "Stopping development services..."
    docker-compose -f docker-compose.dev.yml down
  }
  trap cleanup EXIT
  exit 0
fi

# ─────────────────────────────────────────────────────────────────────────────
#  LOCAL MODE  (no Docker)
# ─────────────────────────────────────────────────────────────────────────────

BACKEND_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$BACKEND_DIR/../.." && pwd)"
FRONTEND_DIR="$PROJECT_ROOT/tabletap-console copy"
ADMIN_DIR="$PROJECT_ROOT/tabletap-admin"

GREEN="\033[0;32m"
YELLOW="\033[1;33m"
RED="\033[0;31m"
CYAN="\033[0;36m"
RESET="\033[0m"

step()  { echo -e "\n${CYAN}▶ $1${RESET}"; }
ok()    { echo -e "${GREEN}  ✓ $1${RESET}"; }
warn()  { echo -e "${YELLOW}  ⚠ $1${RESET}"; }
error() { echo -e "${RED}  ✗ $1${RESET}"; }
info()  { echo -e "    $1"; }

echo ""
echo -e "${CYAN}╔══════════════════════════════════════════╗${RESET}"
echo -e "${CYAN}║   TableTap – Local Development Setup     ║${RESET}"
echo -e "${CYAN}╚══════════════════════════════════════════╝${RESET}"

# ── 1. Prerequisites ──────────────────────────────────────────────────────────
step "Checking prerequisites"

check_cmd() {
  if command -v "$1" &>/dev/null; then
    ok "$1 found ($(command -v "$1"))"
  else
    error "$1 not found – please install it before continuing"
    MISSING=1
  fi
}

MISSING=0
check_cmd python3
check_cmd pip3
check_cmd psql
check_cmd node
check_cmd npm

if [[ $MISSING -eq 1 ]]; then
  echo ""
  error "One or more prerequisites are missing. Aborting."
  exit 1
fi

PYTHON_VER=$(python3 --version 2>&1)
NODE_VER=$(node --version 2>&1)
ok "Python: $PYTHON_VER"
ok "Node:   $NODE_VER"

# ── 2. Backend .env ───────────────────────────────────────────────────────────
step "Backend environment variables (.env)"

ENV_FILE="$BACKEND_DIR/.env"

if [[ ! -f "$ENV_FILE" ]]; then
  warn ".env not found – creating template at $ENV_FILE"
  cat > "$ENV_FILE" <<'ENVTEMPLATE'
# ── Required: copy values from Replit Secrets ──────────────────────────────
SECRET_KEY=your-django-secret-key-here
DEBUG=True

# PostgreSQL – local database
DATABASE_URL=postgres://postgres:postgres@localhost:5432/tabletap_dev

# Clerk – get these from https://dashboard.clerk.com → API Keys
CLERK_SECRET_KEY=sk_test_XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
CLERK_PUBLISHABLE_KEY=pk_test_XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX

# Pusher (optional for local dev – can leave as-is to skip realtime)
PUSHER_APP_ID=
PUSHER_APP_KEY=
PUSHER_APP_SECRET=
PUSHER_CLUSTER=eu

# Resend (optional for local dev – emails will print to console instead)
RESEND_API_KEY=

# Allowed hosts
ALLOWED_HOSTS=localhost,127.0.0.1,0.0.0.0
CORS_ALLOWED_ORIGINS=http://localhost:5173,http://localhost:3000,http://127.0.0.1:5173
ENVTEMPLATE
  echo ""
  warn "ACTION REQUIRED: Fill in SECRET_KEY and CLERK_SECRET_KEY in:"
  info "$ENV_FILE"
  info ""
  info "You can find the Clerk keys at:"
  info "  https://dashboard.clerk.com → Your App → API Keys"
  info ""
  info "Generate a Django secret key with:"
  info "  python3 -c \"import secrets; print(secrets.token_urlsafe(50))\""
  echo ""
  read -rp "Press ENTER once you have filled in the .env file, or Ctrl+C to abort: "
else
  ok ".env found"
fi

# Source the .env so we can use DATABASE_URL
set -a
# shellcheck disable=SC1090
source "$ENV_FILE"
set +a

if [[ -z "$CLERK_SECRET_KEY" || "$CLERK_SECRET_KEY" == "sk_test_XXXXX"* ]]; then
  warn "CLERK_SECRET_KEY looks like the placeholder. Auth will fail until you set a real key."
fi

# ── 3. Frontend .env ──────────────────────────────────────────────────────────
step "Frontend environment variables"

FRONTEND_ENV="$FRONTEND_DIR/.env"
if [[ ! -f "$FRONTEND_ENV" ]]; then
  warn "Creating frontend .env at $FRONTEND_ENV"
  cat > "$FRONTEND_ENV" <<'FENV'
VITE_API_BASE_URL=http://localhost:8000/api
VITE_CLERK_PUBLISHABLE_KEY=pk_test_XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
VITE_PUSHER_APP_KEY=
VITE_PUSHER_CLUSTER=eu
FENV
  warn "ACTION REQUIRED: Set VITE_CLERK_PUBLISHABLE_KEY in $FRONTEND_ENV"
else
  ok "Frontend .env found"
fi

ADMIN_ENV="$ADMIN_DIR/.env"
if [[ -d "$ADMIN_DIR" && ! -f "$ADMIN_ENV" ]]; then
  warn "Creating admin .env at $ADMIN_ENV"
  cat > "$ADMIN_ENV" <<'AENV'
VITE_API_BASE_URL=http://localhost:8000/api
VITE_CLERK_PUBLISHABLE_KEY=pk_test_XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
AENV
  warn "ACTION REQUIRED: Set VITE_CLERK_PUBLISHABLE_KEY in $ADMIN_ENV"
else
  [[ -d "$ADMIN_DIR" ]] && ok "Admin .env found"
fi

# ── 4. Python dependencies ────────────────────────────────────────────────────
step "Installing Python dependencies"

cd "$BACKEND_DIR"

if [[ -f "requirements.txt" ]]; then
  pip3 install -r requirements.txt -q
  ok "Python packages installed"
else
  error "requirements.txt not found in $BACKEND_DIR"
  exit 1
fi

# ── 5. PostgreSQL database ────────────────────────────────────────────────────
step "PostgreSQL – database setup"

# Extract DB name from DATABASE_URL  (postgres://user:pass@host:port/dbname)
DB_NAME=$(echo "$DATABASE_URL" | sed 's|.*\/||' | sed 's|?.*||')
DB_USER=$(echo "$DATABASE_URL" | sed 's|postgres://||' | sed 's|:.*||')
DB_HOST=$(echo "$DATABASE_URL" | sed 's|.*@||' | sed 's|:.*||' | sed 's|/.*||')
DB_PORT=$(echo "$DATABASE_URL" | sed 's|.*:\([0-9]*\)/.*|\1|')
DB_PORT="${DB_PORT:-5432}"

info "Database : $DB_NAME"
info "User     : $DB_USER"
info "Host     : $DB_HOST:$DB_PORT"

if psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -lqt 2>/dev/null | cut -d'|' -f1 | grep -qw "$DB_NAME"; then
  ok "Database '$DB_NAME' already exists"
else
  warn "Database '$DB_NAME' not found – attempting to create it"
  if createdb -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" "$DB_NAME" 2>/dev/null; then
    ok "Database '$DB_NAME' created"
  else
    error "Could not create database '$DB_NAME'."
    info "Run manually:  createdb $DB_NAME"
    info "Or:            psql -U postgres -c \"CREATE DATABASE $DB_NAME;\""
    exit 1
  fi
fi

# ── 6. Django migrations ──────────────────────────────────────────────────────
step "Running Django migrations"

cd "$BACKEND_DIR"

info "Running shared-schema migrations (public schema)..."
python3 manage.py migrate_schemas --shared 2>&1 | tail -5
ok "Shared migrations done"

info "Running tenant-schema migrations..."
python3 manage.py migrate_schemas 2>&1 | tail -5
ok "Tenant migrations done"

# ── 7. Seed local data (public tenant + localhost domains) ────────────────────
step "Seeding local data"

info "Creating public tenant and registering localhost domains..."
python3 manage.py seed_local
ok "Local seed done"

# ── 8. Superadmin setup ───────────────────────────────────────────────────────
step "Super admin setup"

python3 manage.py shell <<'PYEOF'
from authentication.models import User

existing = User.objects.filter(is_staff=True).count()
if existing == 0:
    print("  No staff users found.")
    print("  To mark yourself as super admin after first login, run:")
    print("    python3 manage.py shell -c \"")
    print("      from authentication.models import User")
    print("      u = User.objects.get(email='your@email.com')")
    print("      u.is_staff = True; u.save()\"")
else:
    print(f"  {existing} staff (super admin) user(s) already exist.")
PYEOF

# ── 8. Frontend dependencies ──────────────────────────────────────────────────
step "Installing frontend npm dependencies"

if [[ -f "$FRONTEND_DIR/package.json" ]]; then
  cd "$FRONTEND_DIR"
  npm install --silent
  ok "Console frontend packages installed"
fi

if [[ -d "$ADMIN_DIR" && -f "$ADMIN_DIR/package.json" ]]; then
  cd "$ADMIN_DIR"
  npm install --silent
  ok "Admin frontend packages installed"
fi

# ── 9. Clerk dashboard checklist ──────────────────────────────────────────────
step "Clerk dashboard – required settings"

echo ""
echo -e "${YELLOW}  Before logging in locally, add these to your Clerk dashboard:${RESET}"
echo -e "  (https://dashboard.clerk.com → Configure → Domains & URLs)"
echo ""
echo -e "  Allowed origins:"
echo -e "    http://localhost:5173"
echo -e "    http://localhost:3000"
echo -e "    http://localhost:8000"
echo ""
echo -e "  Allowed redirect URLs:"
echo -e "    http://localhost:5173"
echo -e "    http://localhost:5173/*"
echo -e "    http://localhost:3000"
echo -e "    http://localhost:3000/*"
echo ""

# ── 10. Start servers ─────────────────────────────────────────────────────────
step "Starting development servers"

echo ""
echo -e "${GREEN}  All setup complete. Starting servers:${RESET}"
echo -e "  Backend  →  http://localhost:8000"
echo -e "  Frontend →  http://localhost:5173   (run manually: cd 'tabletap-console copy' && npm run dev)"
echo -e "  Admin    →  http://localhost:3000   (run manually: cd tabletap-admin && npm run dev)"
echo ""
echo -e "  Tip: open three terminal tabs and start each server separately for cleaner logs."
echo ""

cd "$BACKEND_DIR"
python3 manage.py runserver 0.0.0.0:8000
