# PostgreSQL Database Integration

This document provides a comprehensive overview of the PostgreSQL database integration for the HoardRun Fintech Backend.

## Overview

The application uses PostgreSQL as the primary database with SQLAlchemy as the ORM and Alembic for database migrations. The integration includes:

- **Production-ready PostgreSQL configuration**
- **Comprehensive database models with validation**
- **Database health monitoring**
- **Automated migration system**
- **Database initialization scripts**
- **Comprehensive test suite**

## Database Configuration

### Environment Variables

The following environment variables control database behavior:

```bash
# Required
DATABASE_URL=postgresql://user:password@host:port/database

# Connection Pool Configuration
DATABASE_POOL_SIZE=20                    # Connection pool size
DATABASE_MAX_OVERFLOW=30                 # Max overflow connections
DATABASE_POOL_TIMEOUT=30                 # Pool timeout in seconds
DATABASE_POOL_RECYCLE=3600              # Connection recycle time in seconds
DATABASE_POOL_PRE_PING=true             # Enable pre-ping
DATABASE_ECHO=false                      # Enable SQL query logging
DATABASE_SSL_MODE=prefer                 # PostgreSQL SSL mode
DATABASE_CONNECT_TIMEOUT=10              # Connection timeout in seconds
DATABASE_COMMAND_TIMEOUT=60              # Command timeout in seconds
```

### SSL Configuration

The database supports various SSL modes:
- `disable`: No SSL
- `allow`: SSL if available
- `prefer`: SSL preferred (default)
- `require`: SSL required
- `verify-ca`: SSL with CA verification
- `verify-full`: SSL with full verification

## Database Models

### Core Models

1. **User**: User accounts with authentication and profile information
2. **Account**: Financial accounts (checking, savings, investment, etc.)
3. **Transaction**: Financial transactions with comprehensive tracking
4. **Card**: Payment cards with security features
5. **Investment**: Investment holdings and portfolio tracking
6. **P2PTransaction**: Peer-to-peer money transfers
7. **Transfer**: Account-to-account transfers

### Model Features

- **Validation**: Comprehensive field validation using SQLAlchemy validators
- **Constraints**: Database-level constraints for data integrity
- **Indexes**: Optimized indexes for query performance
- **Relationships**: Proper foreign key relationships with cascade options
- **Enums**: Type-safe enumerations for status fields

### Example Model Usage

```python
from app.database.models import User, Account, AccountTypeEnum

# Create a user
user = User(
    email="user@example.com",
    first_name="John",
    last_name="Doe",
    phone_number="+1234567890",
    password_hash="hashed_password"
)

# Create an account
account = Account(
    user_id=user.id,
    account_number="ACC1234567890",
    account_name="Primary Checking",
    account_type=AccountTypeEnum.CHECKING,
    currency="USD"
)
```

## Database Migrations

### Alembic Configuration

Migrations are managed using Alembic with the following structure:

```
fintech_backend/
├── alembic/
│   ├── versions/           # Migration files
│   ├── env.py             # Alembic environment
│   └── script.py.mako     # Migration template
└── alembic.ini            # Alembic configuration
```

### Migration Commands

```bash
# Create a new migration
alembic revision --autogenerate -m "Description of changes"

# Run migrations
alembic upgrade head

# Check migration history
alembic history

# Downgrade to previous version
alembic downgrade -1
```

## Database Initialization

### Initialization Scripts

The `scripts/` directory contains tools for database setup:

1. **init_database.py**: Python script for database initialization
2. **init_db.sh**: Shell script wrapper (Linux/macOS)
3. **init_db.bat**: Batch file wrapper (Windows)

### Usage Examples

```bash
# Check database connection
./scripts/init_db.sh check

# Initialize database with migrations
./scripts/init_db.sh init

# Initialize with sample data (development)
./scripts/init_db.sh sample

# Reset database (development only)
./scripts/init_db.sh reset
```

### Windows Usage

```cmd
REM Check database connection
scripts\init_db.bat check

REM Initialize database
scripts\init_db.bat init

REM Initialize with sample data
scripts\init_db.bat sample
```

## Health Monitoring

### Health Check Endpoints

The application provides comprehensive health check endpoints:

- `GET /api/health/`: Basic health check
- `GET /api/health/detailed`: Detailed system information
- `GET /api/health/database`: Database-specific health check
- `GET /api/health/readiness`: Kubernetes readiness probe
- `GET /api/health/liveness`: Kubernetes liveness probe

### Example Health Check Response

```json
{
  "status": "healthy",
  "timestamp": "2023-10-13T10:30:00Z",
  "database": {
    "database_url": "postgresql://***",
    "database_version": "PostgreSQL 14.9",
    "connection_healthy": true,
    "pool_info": {
      "pool_size": 20,
      "checked_in": 18,
      "checked_out": 2,
      "overflow": 0
    }
  }
}
```

## Testing

### Test Structure

```
tests/
├── integration/
│   ├── test_database.py           # Database model tests
│   ├── test_health_endpoints.py   # Health endpoint tests
│   └── test_database_init.py      # Initialization script tests
└── conftest.py                    # Test configuration and fixtures
```

### Running Tests

```bash
# Run all database tests
python scripts/run_tests.py --database-only

# Run with coverage
python scripts/run_tests.py --coverage

# Run specific test file
python scripts/run_tests.py --specific tests/integration/test_database.py

# Run specific test suites
python scripts/run_tests.py --specific-tests
```

### Test Features

- **Isolated test database**: Each test uses a clean SQLite database
- **Comprehensive fixtures**: Pre-configured test data
- **Model validation testing**: Ensures data integrity
- **Relationship testing**: Verifies foreign key relationships
- **Health endpoint testing**: Validates monitoring functionality

## Performance Optimization

### Connection Pooling

The database uses connection pooling for optimal performance:

- **Pool Size**: 20 connections (configurable)
- **Max Overflow**: 30 additional connections
- **Pool Timeout**: 30 seconds
- **Connection Recycling**: 1 hour
- **Pre-ping**: Validates connections before use

### Indexing Strategy

Indexes are strategically placed on:

- **Primary keys**: All models have UUID primary keys
- **Foreign keys**: All relationship fields are indexed
- **Query fields**: Commonly queried fields (email, phone, status)
- **Composite indexes**: Multi-column indexes for complex queries
- **Date fields**: Transaction dates and timestamps

### Query Optimization

- **Eager loading**: Relationships loaded efficiently
- **Pagination**: Built-in pagination support
- **Filtering**: Indexed fields for fast filtering
- **Aggregation**: Optimized for financial calculations

## Security Considerations

### Data Protection

- **Password hashing**: Secure password storage
- **Sensitive data**: Masked card numbers, encrypted tokens
- **SQL injection**: Parameterized queries via SQLAlchemy
- **Connection security**: SSL/TLS encryption

### Access Control

- **User roles**: Role-based access control
- **Account ownership**: Users can only access their data
- **Transaction integrity**: Immutable transaction records
- **Audit trails**: Comprehensive logging

## Deployment

### Production Checklist

- [ ] Database URL configured with SSL
- [ ] Connection pool sized appropriately
- [ ] Migrations applied
- [ ] Health checks configured
- [ ] Monitoring set up
- [ ] Backup strategy implemented
- [ ] SSL certificates valid

### Environment-Specific Configuration

```bash
# Development
DATABASE_POOL_SIZE=5
DATABASE_ECHO=true
DATABASE_SSL_MODE=prefer

# Production
DATABASE_POOL_SIZE=20
DATABASE_ECHO=false
DATABASE_SSL_MODE=require
```

## Troubleshooting

### Common Issues

1. **Connection Refused**
   - Check database server is running
   - Verify connection string
   - Check firewall settings

2. **SSL Connection Issues**
   - Verify SSL mode configuration
   - Check certificate validity
   - Ensure server supports SSL

3. **Migration Failures**
   - Check database permissions
   - Verify migration file syntax
   - Review constraint conflicts

4. **Performance Issues**
   - Monitor connection pool usage
   - Check query execution plans
   - Review index usage

### Debugging

```bash
# Enable SQL query logging
DATABASE_ECHO=true

# Check database connection
python scripts/init_database.py --check-only --verbose

# Run health checks
curl http://localhost:8000/api/health/database

# Check migration status
alembic current
alembic history
```

## Support

For database-related issues:

1. Check the health endpoints for system status
2. Review application logs for error details
3. Verify environment variable configuration
4. Test database connectivity using the init scripts
5. Check migration status and history

## Future Enhancements

- **Read replicas**: Support for read-only database replicas
- **Sharding**: Horizontal scaling for large datasets
- **Caching**: Redis integration for frequently accessed data
- **Analytics**: Dedicated analytics database
- **Backup automation**: Automated backup and restore procedures
