# TableTap Console Backend - Development Guide

## 🚀 Quick Start

### Prerequisites
- Docker & Docker Compose

### 1. Run Development Environment
```bash
# Simple way - starts everything (PostgreSQL, Redis, Django)
./dev.sh

# Or manually
docker-compose -f docker-compose.dev.yml up --build
```

### 2. Access Your Application
- **Backend API**: http://localhost:3001
- **Django Admin**: http://localhost:3001/admin
- **PostgreSQL**: localhost:5435 (separate from any existing PostgreSQL)
- **Redis**: localhost:6379

## 📁 Development Setup

### File Structure
```
tabletap-console-backend/
├── Dockerfile              # Development Dockerfile with volume mounts
├── Dockerfile.prod         # Production Dockerfile
├── docker-compose.yml      # Original compose file
├── docker-compose.dev.yml  # Development compose file
├── dev.sh                  # Development startup script
└── ...
```

### Volume Mounts
The development setup mounts your local code into the container:
- **Source Code**: `.:/app` - Live code editing
- **Cache Exclusions**: Excludes `__pycache__` and `.pytest_cache`

## 🛠️ Development Features

### Auto-Reload
- Django development server with auto-reload
- Celery worker with `--reload` flag
- Changes to Python files trigger automatic restarts

### Development Tools Included
- `django-extensions` - Enhanced Django commands
- `ipython` - Better Python shell
- `watchdog` - File system monitoring

### Database Connection
- Self-contained PostgreSQL service (no external dependencies)
- Database: `tabletap_console` on port 5435
- Persistent data with Docker volumes

## 🔧 Available Services

### Web Service
- **Port**: 3001 (maps to container port 8000)
- **Auto-reload**: ✅
- **Volume Mount**: ✅

### Redis Service
- **Port**: 6379
- **Persistent Data**: ✅

### Celery Worker (Optional)
- **Auto-reload**: ✅
- **Volume Mount**: ✅

### Celery Beat (Optional)
- **Scheduled Tasks**: ✅
- **Volume Mount**: ✅

## 📝 Common Commands

### Start Development
```bash
./dev.sh
```

### Stop Development
```bash
docker-compose -f docker-compose.dev.yml down
```

### View Logs
```bash
docker-compose -f docker-compose.dev.yml logs -f web
```

### Run Django Commands
```bash
# Migrations
docker-compose -f docker-compose.dev.yml exec web python manage.py migrate

# Create superuser
docker-compose -f docker-compose.dev.yml exec web python manage.py createsuperuser

# Django shell
docker-compose -f docker-compose.dev.yml exec web python manage.py shell
```

### Rebuild Containers
```bash
docker-compose -f docker-compose.dev.yml build --no-cache
```

## 🔧 Available Services

### Web Service
- **Port**: 3001 (maps to container port 8000)
- **Auto-reload**: ✅
- **Volume Mount**: ✅

### Database Service
- **Port**: 5435 (separate from any existing PostgreSQL)
- **Persistent Data**: ✅
- **Health Check**: ✅

### Redis Service
- **Port**: 6379
- **Persistent Data**: ✅

### Celery Worker (Optional)
- **Auto-reload**: ✅
- **Volume Mount**: ✅

### Celery Beat (Optional)
- **Scheduled Tasks**: ✅
- **Volume Mount**: ✅

## 🐛 Troubleshooting

### Database Connection Issues
1. Check if all services are running:
   ```bash
   docker-compose -f docker-compose.dev.yml ps
   ```

2. Check database health:
   ```bash
   docker-compose -f docker-compose.dev.yml exec db pg_isready -U postgres
   ```

### Permission Issues
The Dockerfile creates a non-root `app` user for security. If you encounter permission issues:
```bash
# Fix ownership
sudo chown -R $USER:$USER .
```

### Container Won't Start
1. Check logs:
   ```bash
   docker-compose -f docker-compose.dev.yml logs web
   ```

2. Rebuild without cache:
   ```bash
   docker-compose -f docker-compose.dev.yml build --no-cache
   ```

## 🚀 Production Deployment

Use `Dockerfile.prod` for production builds:
```bash
docker build -f Dockerfile.prod -t tabletap-console-backend:prod .
```

## 💡 Tips

1. **Code Changes**: Edit files locally, changes reflect immediately in container
2. **Database**: Use your existing PostgreSQL container
3. **Debugging**: Add `import pdb; pdb.set_trace()` for debugging
4. **Performance**: Volume mounts may be slower on macOS, consider using Docker Desktop's new features
