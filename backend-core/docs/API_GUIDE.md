# How to Use PhotoGear API

## Quick Start Guide

### 1. **View Available APIs**

Once your server is running at `http://localhost:8000`, you can access:

- **API Root**: http://localhost:8000/
  - Shows all available endpoints
  
- **API Documentation**: http://localhost:8000/docs/
  - Complete API documentation with examples

- **Admin Panel**: http://localhost:8000/admin/
  - Django admin interface (requires superuser)

---

## Testing the API

### Method 1: Using your Browser (for GET requests)

Simply visit:
- http://localhost:8000/ - API root
- http://localhost:8000/docs/ - Documentation
- http://localhost:8000/v1/accounts/profile/ - Profile (needs authentication)

### Method 2: Using curl (Command Line)

#### Register a new user:
```bash
curl -X POST http://localhost:8000/v1/accounts/register/ \
  -H "Content-Type: application/json" \
  -d '{
    "email": "test@example.com",
    "password": "testpass123",
    "confirm_password": "testpass123",
    "first_name": "Test",
    "last_name": "User"
  }'
```

#### Login:
```bash
curl -X POST http://localhost:8000/v1/accounts/login/ \
  -H "Content-Type: application/json" \
  -d '{
    "email": "test@example.com",
    "password": "testpass123"
  }'
```

Save the `access` token from the response!

#### Get your profile (authenticated):
```bash
curl -X GET http://localhost:8000/v1/accounts/profile/ \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN_HERE"
```

### Method 3: Using Python

```python
import requests

# Base URL
BASE_URL = "http://localhost:8000"

# 1. Register
response = requests.post(f"{BASE_URL}/v1/accounts/register/", json={
    "email": "test@example.com",
    "password": "testpass123",
    "confirm_password": "testpass123"
})
print("Register:", response.json())

# 2. Login
response = requests.post(f"{BASE_URL}/v1/accounts/login/", json={
    "email": "test@example.com",
    "password": "testpass123"
})
data = response.json()
access_token = data['data']['access']
print("Login successful, token:", access_token[:20] + "...")

# 3. Get profile (authenticated)
headers = {"Authorization": f"Bearer {access_token}"}
response = requests.get(f"{BASE_URL}/v1/accounts/profile/", headers=headers)
print("Profile:", response.json())

# 4. Create organizations
response = requests.post(
    f"{BASE_URL}/v1/accounts/organizations/create/",
    headers=headers,
    json={
        "name": "My Organization",
        "description": "Test organizations"
    }
)
print("Organization:", response.json())

# 5. List organizations
response = requests.get(
    f"{BASE_URL}/v1/accounts/organizations/list/",
    headers=headers
)
print("Organizations:", response.json())
```

### Method 4: Using Postman or Insomnia

1. Import the following as a collection:
   - Base URL: `http://localhost:8000`
   - Add requests for each endpoint from http://localhost:8000/docs/

2. For authenticated requests:
   - Add header: `Authorization: Bearer <your_token>`

---

## Available Endpoints

### **Authentication** (No auth required)

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/v1/accounts/register/` | Register new user |
| POST | `/v1/accounts/login/` | Login and get JWT token |

### **User Profile** (Auth required)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/v1/accounts/profile/` | Get current user info |

### **Organizations** (Auth required)

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/v1/accounts/organizations/create/` | Create organization |
| GET | `/v1/accounts/organizations/list/` | List all organizations |
| GET | `/v1/accounts/organizations/detail/{id}/` | Get organization by ID |

### **Datasets** (Auth required)

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/v1/datasets/create/` | Create dataset |
| GET | `/v1/datasets/list/` | List all datasets |
| GET | `/v1/datasets/detail/{id}/` | Get dataset by ID |

---

## Response Format

All API responses follow this format:

**Success:**
```json
{
  "data": { ... },
  "error": null,
  "is_success": true
}
```

**Error:**
```json
{
  "data": null,
  "error": "Error message",
  "is_success": false
}
```

---

## Authentication Flow

1. **Register** → Get user created
2. **Login** → Get `access` and `refresh` tokens
3. **Use access token** in header: `Authorization: Bearer <access_token>`
4. When token expires, use refresh token to get new access token

---

## Common Query Parameters

- `page` - Page number for pagination (default: 1)
- `page_size` - Items per page (default: 100)
- `ordering` - Sort by field (use `-` for descending, e.g., `-created_at`)
- Filter by any field (e.g., `?name=test&platform=DJI`)

---

## Tips

1. **Browse with Django REST Framework UI**: 
   - Visit endpoints in browser to see interactive forms
   - Works great for testing without writing code!

2. **Check Admin Panel**:
   - Create superuser: `python manage.py createsuperuser`
   - Access: http://localhost:8000/admin/
   - Manually view/edit all data

3. **Use the built-in docs**:
   - http://localhost:8000/ - Quick overview
   - http://localhost:8000/docs/ - Full documentation

4. **Enable DEBUG mode**:
   - Set `DEBUG=True` in settings for detailed error messages

---

## Example Workflow

```bash
# 1. Start server
python manage.py runserver

# 2. In another terminal, register
curl -X POST http://localhost:8000/v1/accounts/register/ \
  -H "Content-Type: application/json" \
  -d '{"email": "demo@test.com", "password": "demo123456", "confirm_password": "demo123456"}'

# 3. Login
curl -X POST http://localhost:8000/v1/accounts/login/ \
  -H "Content-Type: application/json" \
  -d '{"email": "demo@test.com", "password": "demo123456"}'

# Copy the access token from response

# 4. Use authenticated endpoints
TOKEN="your_access_token_here"

curl -X GET http://localhost:8000/v1/accounts/profile/ \
  -H "Authorization: Bearer $TOKEN"

curl -X GET http://localhost:8000/v1/accounts/organizations/list/ \
  -H "Authorization: Bearer $TOKEN"
```

---

## Need More Help?

- Check `/docs/backend-api-spec.md` for detailed API specification
- Visit http://localhost:8000/docs/ for interactive documentation
- Use Django admin panel for data inspection
- Check Django logs for error details
