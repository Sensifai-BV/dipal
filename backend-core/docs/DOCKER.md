# Docker Setup for PhotoGear Backend

This project uses Docker Compose to run the Django application with PostgreSQL database.

## Prerequisites

- Docker
- Docker Compose

## Quick Start

1. **Build and start the containers:**
   ```bash
   docker-compose up --build
   ```

2. **Access the application:**
   - API: http://localhost:8000
   - Admin: http://localhost:8000/admin/

3. **Stop the containers:**
   ```bash
   docker-compose down
   ```

## Useful Commands

### Create a superuser
```bash
docker-compose exec web python manage.py createsuperuser
```

### Run migrations
```bash
docker-compose exec web python manage.py migrate
```

### Access Django shell
```bash
docker-compose exec web python manage.py shell
```

### View logs
```bash
docker-compose logs -f web
docker-compose logs -f db
```

### Access PostgreSQL database
```bash
docker-compose exec db psql -U photogear_user -d photogear
```

### Run tests
```bash
docker-compose exec web python manage.py test
```

### Collect static files
```bash
docker-compose exec web python manage.py collectstatic --noinput
```

## Environment Variables

The application uses the following environment variables (defined in docker-compose.yml):

- `DEBUG`: Enable/disable debug mode
- `SECRET_KEY`: Django secret key
- `DB_ENGINE`: Database engine (postgresql)
- `DB_NAME`: Database name
- `DB_USER`: Database user
- `DB_PASSWORD`: Database password
- `DB_HOST`: Database host (service name)
- `DB_PORT`: Database port

## Development

For development, the project directory is mounted as a volume, so changes to the code will be reflected immediately.

### Rebuild after dependency changes
```bash
docker-compose up --build
```

### Stop and remove volumes (WARNING: deletes database data)
```bash
docker-compose down -v
```

## Production Notes

For production deployment:

1. Change `DEBUG=False` in environment variables
2. Use a strong `SECRET_KEY`
3. Update `ALLOWED_HOSTS` to your domain
4. Use proper PostgreSQL credentials
5. Set up proper volume backups for the database
6. Consider using environment file instead of hardcoded values in docker-compose.yml

## Database Backups

### Backup database
```bash
docker-compose exec db pg_dump -U photogear_user photogear > backup.sql
```

### Restore database
```bash
docker-compose exec -T db psql -U photogear_user photogear < backup.sql
```

## Troubleshooting

### Port already in use
If port 8000 or 5432 is already in use, modify the ports in docker-compose.yml:
```yaml
ports:
  - "8001:8000"  # Change 8001 to any available port
```

### Database connection issues
Ensure the database service is healthy before the web service starts. The healthcheck in docker-compose.yml handles this automatically.

### Permission issues
If you encounter permission issues, ensure proper ownership:
```bash
sudo chown -R $USER:$USER .
```
