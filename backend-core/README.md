# PhotoGear Backend

Django REST API for the PhotoGear photogrammetry platform.

## Features

- **User Authentication**: JWT-based authentication with email login
- **Organization Management**: Multi-tenant organization structure
- **Dataset Management**: Handle drone imagery collections with metadata
- **RESTful API**: Complete REST API with filtering, pagination, and ordering
- **Admin Interface**: Django admin panels for all models
- **PostgreSQL Database**: Production-ready database with Docker support

## Tech Stack

- Python 3.13
- Django 5.2
- Django REST Framework
- PostgreSQL 16
- JWT Authentication
- Docker & Docker Compose

## Quick Start with Docker (Recommended)

1. **Start the application:**
   ```bash
   docker-compose up --build
   ```

2. **Create a superuser:**
   ```bash
   make createsuperuser
   ```

3. **Access the application:**
   - API: http://localhost:8000
   - Admin: http://localhost:8000/admin/
   - API Docs: See `docs/backend-api-spec.md`

## Alternative: Local Development

1. **Install dependencies:**
   ```bash
   pip install -e .
   ```

2. **Run migrations:**
   ```bash
   python manage.py migrate
   ```

3. **Create superuser:**
   ```bash
   python manage.py createsuperuser
   ```

4. **Run development server:**
   ```bash
   python manage.py runserver
   ```

## API Endpoints

### Authentication
- `POST /v1/accounts/login/` - User login
- `POST /v1/accounts/register/` - User registration
- `GET /v1/accounts/profile/` - Get user profile

### Organizations
- `POST /v1/accounts/organizations/create/` - Create organization
- `GET /v1/accounts/organizations/list/` - List organizations
- `GET /v1/accounts/organizations/detail/<id>/` - Organization details

### Datasets
- `POST /v1/datasets/create/` - Create dataset
- `GET /v1/datasets/list/` - List datasets
- `GET /v1/datasets/detail/<id>/` - Dataset details

## Docker Commands

Use the Makefile for convenience:

```bash
make help           # Show all available commands
make build          # Build Docker images
make up             # Start all services
make down           # Stop all services
make logs           # View logs
make shell          # Open Django shell
make migrate        # Run migrations
make createsuperuser# Create domain user
make test           # Run tests
```

See [DOCKER.md](DOCKER.md) for detailed Docker documentation.

## Project Structure

```
backend/
├── accounts/           # User authentication and organizations
├── datasets/           # Dataset management
├── products/           # Products (future)
├── config/            # Django configuration
├── docs/              # API documentation
├── utils/             # Shared utilities
├── docker-compose.yml # Docker setup
├── Dockerfile         # Docker image
└── Makefile          # Convenience commands
```

## Documentation

- [Backend API Specification](docs/backend-api-spec.md)
- [Image Analysis API Spec](docs/image-analysis-api-spec.md)
- [Entity Relationship Diagram](docs/entity-relationship-diagram.md)
- [Docker Setup Guide](DOCKER.md)
- [Accounts App README](accounts/README.md)

## Environment Variables

Key environment variables (see `.env.example`):

- `DEBUG`: Enable debug mode
- `SECRET_KEY`: Django secret key
- `DB_ENGINE`: Database engine
- `DB_NAME`: Database name
- `DB_USER`: Database user
- `DB_PASSWORD`: Database password
- `DB_HOST`: Database host
- `DB_PORT`: Database port

## Testing

Run tests with:
```bash
# With Docker
make test

# Without Docker
python manage.py test
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Run tests
5. Submit a pull request

## License

Proprietary - PhotoGear


