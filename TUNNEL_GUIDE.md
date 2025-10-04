# 🌐 Tunnel Configuration Guide

## ✅ **Fixed Configuration**

Your Django app is now configured to work with tunneling services like `loca.lt`, `ngrok`, etc.

### Changes Made:

1. **ALLOWED_HOSTS** - Added tunnel domain patterns:
   ```python
   ALLOWED_HOSTS = ['localhost', '127.0.0.1', '*.loca.lt', '*.ngrok.io', '*.tunnelmole.com']
   ```

2. **CORS Settings** - Allow all origins in development:
   ```python
   if DEBUG:
       CORS_ALLOW_ALL_ORIGINS = True
       CORS_ALLOW_CREDENTIALS = True
   ```

3. **CSRF Protection** - Added trusted tunnel origins:
   ```python
   CSRF_TRUSTED_ORIGINS = [
       'https://*.loca.lt',
       'https://*.ngrok.io',
       # ... other domains
   ]
   ```

## 🚀 **How to Use**

### 1. Start Your Development Server
```bash
./dev.sh
# Your Django API will be running on localhost:3001
```

### 2. Create a Tunnel
```bash
# Using loca.lt (free)
npx localtunnel --port 3001 --subdomain ttc-app

# Using ngrok (requires account)
ngrok http 3001

# Using tunnelmole (free)
npx tunnelmole 3001
```

### 3. Test Configuration
```bash
# Test if your Django settings are correct
python test_tunnel.py
```

### 4. Access Your API
Your tunnel URL should now work:
- `https://ttc-app.loca.lt/` - Your API root
- `https://ttc-app.loca.lt/admin/` - Django admin
- `https://ttc-app.loca.lt/api/` - Your API endpoints

## 🔧 **Troubleshooting**

### Still Getting 404?
1. **Check Django is running**: Visit `http://localhost:3001` first
2. **Restart Django**: After changing settings, restart your containers
3. **Test configuration**: Run `python test_tunnel.py`

### CORS Issues?
- Development mode allows all origins
- Check browser console for CORS errors
- Ensure `CORS_ALLOW_ALL_ORIGINS = True` in development

### CSRF Issues?
- Added `*.loca.lt` to `CSRF_TRUSTED_ORIGINS`
- For API calls, you may need to disable CSRF for API endpoints

## 📝 **Common Tunnel Commands**

```bash
# loca.lt with custom subdomain
npx localtunnel --port 3001 --subdomain your-app-name

# ngrok with custom domain (paid)
ngrok http 3001 --hostname=your-domain.ngrok.io

# tunnelmole (simple)
npx tunnelmole 3001
```

## 🔒 **Security Notes**

- These settings are for **development only**
- In production, use specific domain names in `ALLOWED_HOSTS`
- Never use `CORS_ALLOW_ALL_ORIGINS = True` in production
- Consider using environment-specific settings files

## ✅ **Ready to Go!**

Your Django backend should now work perfectly with any tunneling service. The configuration is flexible and supports multiple tunnel providers.
