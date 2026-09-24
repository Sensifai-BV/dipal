# Accounts Application

This Django application handles user authentication, registration, and profile management for the PhotoGear project.

## Features

- User registration with email verification
- JWT-based authentication (login/logout)
- User profile management
- Custom user model with email as primary identifier
- Asynchronous API endpoints

## Models

### UserModel
Custom user model extending [AbstractUser](file://C:\Projects\python\PythonProject\PhotoGear\.venv\Lib\site-packages\django\contrib\auth\models.py#L445-L513) with the following fields:
- [username](file://C:\Projects\python\PythonProject\PhotoGear\accounts\models\user.py#L9-L13): UUIDField (unique, auto-generated)
- [email](file://C:\Projects\python\PythonProject\PhotoGear\accounts\models\user.py#L14-L16): EmailField (unique, used as USERNAME_FIELD)
- [is_email_verified](file://C:\Projects\python\PythonProject\PhotoGear\accounts\models\user.py#L17-L19): BooleanField (default: False)
- Inherits all standard Django user fields (first_name, last_name, etc.)

## API Endpoints

### Authentication
- `POST /api/accounts/login/` - User login, returns JWT tokens
- `POST /api/accounts/register/` - User registration
- `GET /api/accounts/profile/` - Get authenticated user profile

### Registration Flow
1. User submits email, password, and personal info
2. System creates user account with hashed password
3. (Future implementation) Email verification sent to user

### Login Flow
1. User provides email and password
2. System authenticates credentials
3. Returns access and refresh JWT tokens with expiration times

## Serializers

- [AccountLoginSerializer](file://C:\Projects\python\PythonProject\PhotoGear\accounts\serializers\login.py#L3-L10): Handles login data validation
- [AccountRegisterSerializer](file://C:\Projects\python\PythonProject\PhotoGear\accounts\serializers\register.py#L7-L35): Handles registration data validation and user creation
- [AccountUserModelSerializer](file://C:\Projects\python\PythonProject\PhotoGear\accounts\serializers\user.py#L5-L15): Serializes user profile data

## Dependencies

- Django REST Framework
- Simple JWT for token authentication
- ADRF (Async Django REST Framework) for async views
- Custom user model implementation

## Permissions

- Registration and login endpoints are publicly accessible
- Profile endpoint requires authentication

## Customizations

- Uses email instead of username for authentication
- UUID-based usernames for uniqueness
- All views implemented as async for better performance
- Custom response format with data/error fields