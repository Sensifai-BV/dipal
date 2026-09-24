# PhotoGear API - Postman Collection

This directory contains Postman collection and environment files for testing the PhotoGear Backend API.

## Files

1. **PhotoGear_API.postman_collection.json** - Complete API collection with all endpoints
2. **PhotoGear_Local.postman_environment.json** - Local development environment
3. **PhotoGear_Production.postman_environment.json** - Production environment template

## 📥 Import into Postman

### Method 1: Import Collection

1. Open Postman
2. Click **Import** button (top left)
3. Drag and drop `PhotoGear_API.postman_collection.json` or click to browse
4. Click **Import**

### Method 2: Import Environment

1. Click the **Environments** icon (left sidebar, gear icon)
2. Click **Import**
3. Select `PhotoGear_Local.postman_environment.json`
4. Click **Import**
5. (Optional) Repeat for Production environment

### Method 3: Import All at Once

1. Click **Import**
2. Select all three JSON files at once
3. Click **Import**

## 🚀 Quick Start

### 1. Set the Environment

- Click the environment dropdown (top right)
- Select **"PhotoGear - Local Development"**

### 2. Test the API

The collection is organized into folders:

#### **Authentication** (No auth required)
- ✅ Register User
- ✅ Login (automatically saves token!)
- 🔐 Get Profile

#### **Organizations** (Auth required)
- Create Organization
- List Organizations
- Get Organization Detail

#### **Datasets** (Auth required)
- Create Dataset
- List Datasets
- Get Dataset Detail

#### **API Info**
- API Root
- API Documentation

### 3. Workflow

1. **Register a User** (or skip if you have an account)
   - Open "Authentication" → "Register User"
   - Click **Send**
   - User is created!

2. **Login**
   - Open "Authentication" → "Login"
   - Update email/password in body if needed
   - Click **Send**
   - ✨ **Token is automatically saved to environment!**

3. **Use Authenticated Endpoints**
   - All other endpoints automatically use the saved token
   - Just click **Send** on any request!

## 🔑 Authentication

### Automatic Token Management

The Login request includes a script that automatically saves the access token to your environment:

```javascript
if (pm.response.code === 200) {
    var jsonData = pm.response.json();
    pm.environment.set("access_token", jsonData.data.access);
    pm.environment.set("refresh_token", jsonData.data.refresh);
}
```

All authenticated requests use: `Authorization: Bearer {{access_token}}`

### Manual Token Setup (if needed)

1. Login to get your token
2. Copy the `access` token from response
3. Go to Environments → PhotoGear - Local Development
4. Paste token into `access_token` variable
5. Save

## 📋 Collection Features

### Variables

The collection uses these variables:

- `{{base_url}}` - API base URL (http://localhost:8000 for local)
- `{{access_token}}` - JWT access token (auto-populated on login)
- `{{refresh_token}}` - JWT refresh token (auto-populated on login)

### Query Parameters

Many endpoints support optional query parameters (disabled by default):

**List Endpoints:**
- `page` - Page number for pagination
- `ordering` - Sort by field (prefix with `-` for descending)
- Field filters - Filter by any field (e.g., `name`, `platform`)

Example: `/v1/datasets/list/?page=2&ordering=-created_at&platform=DJI`

### Path Variables

Some endpoints use path variables:

- `:id` - Replace with actual ID (e.g., organization ID, dataset ID)

## 🌐 Environments

### Local Development

```json
{
  "base_url": "http://localhost:8000",
  "user_email": "demo@example.com",
  "user_password": "demo123456"
}
```

### Production

```json
{
  "base_url": "https://api.photogear.com",
  "user_email": "",
  "user_password": ""
}
```

## 📝 Example Requests

### Register and Login

1. **Register:**
   ```json
   POST {{base_url}}/v1/accounts/register/
   {
     "email": "user@example.com",
     "password": "password123",
     "confirm_password": "password123"
   }
   ```

2. **Login:**
   ```json
   POST {{base_url}}/v1/accounts/login/
   {
     "email": "user@example.com",
     "password": "password123"
   }
   ```

3. **Use Token:**
   - Token is automatically added to all requests
   - Header: `Authorization: Bearer {{access_token}}`

### Create Resources

1. **Create Organization:**
   ```json
   POST {{base_url}}/v1/accounts/organizations/create/
   Headers: Authorization: Bearer {{access_token}}
   {
     "name": "My Organization",
     "description": "Optional description"
   }
   ```

2. **Create Dataset:**
   ```json
   POST {{base_url}}/v1/datasets/create/
   Headers: Authorization: Bearer {{access_token}}
   {
     "name": "Field Survey",
     "organizations": 1,
     "platform": "DJI Mavic 3M",
     "capture_start": "2025-10-01T10:00:00Z",
     "capture_end": "2025-10-01T12:00:00Z",
     "crs": "EPSG:32639",
     "bbox": {},
     "notes": "Morning flight"
   }
   ```

## 🎯 Tips

1. **Organize Requests**: Use folders to keep your workspace clean
2. **Save Responses**: Right-click response → Save as Example
3. **Use Variables**: Store commonly used values in environment
4. **Test Scripts**: Add assertions to verify responses
5. **Documentation**: Add descriptions to your requests

## 🔧 Troubleshooting

### "Unauthorized" Error
- Make sure you've logged in and token is saved
- Check environment is selected (top right dropdown)
- Verify `access_token` variable is set in environment

### "Not Found" Error
- Check the URL is correct
- Verify base_url in environment
- Ensure Django server is running

### Connection Error
- Ensure Django development server is running
- Check port 8000 is not blocked
- Verify `base_url` matches your server address

## 📚 Additional Resources

- API Documentation: http://localhost:8000/docs/
- API Root: http://localhost:8000/
- Admin Panel: http://localhost:8000/admin/
- Detailed Spec: See `docs/backend-api-spec.md`

## 🔄 Updating the Collection

If API endpoints change:

1. Update the collection JSON file
2. Re-import in Postman
3. Postman will merge changes automatically

## 💡 Pro Tips

### 1. Pre-request Scripts
Add to collection for automatic headers:
```javascript
pm.request.headers.add({
    key: 'Content-Type',
    value: 'application/json'
});
```

### 2. Test Scripts
Verify responses automatically:
```javascript
pm.test("Status is 200", function () {
    pm.response.to.have.status(200);
});

pm.test("Has data field", function () {
    pm.expect(pm.response.json()).to.have.property('data');
});
```

### 3. Environment Switching
- Quickly switch between local and production
- Use same collection for all environments
- Keep credentials separate and secure

---

**Happy Testing! 🚀**
