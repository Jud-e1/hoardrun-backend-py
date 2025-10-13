# Database Scripts

This directory contains scripts for database initialization, migration, and management.

## Scripts Overview

### `init_database.py`
The main Python script for database operations. Provides comprehensive database initialization and management capabilities.

**Features:**
- Database connection verification
- Alembic migration execution
- Sample data creation for development
- Database reset functionality (development only)
- Verbose logging options

**Usage:**
```bash
python scripts/init_database.py [options]
```

**Options:**
- `--check-only`: Only check database connection, don't run migrations
- `--force-reset`: Drop all tables and recreate (DANGEROUS - use with caution)
- `--create-sample-data`: Create sample data for development
- `--verbose`: Enable verbose logging

### `init_db.sh` (Linux/macOS)
Shell script wrapper for convenient database operations on Unix-like systems.

**Usage:**
```bash
./scripts/init_db.sh [COMMAND] [OPTIONS]
```

**Commands:**
- `check`: Check database connection only
- `init`: Initialize database with migrations
- `reset`: Reset database (DANGEROUS - development only)
- `sample`: Initialize database and create sample data
- `migrate`: Run migrations only

**Examples:**
```bash
./scripts/init_db.sh check                    # Check database connection
./scripts/init_db.sh init                     # Initialize database
./scripts/init_db.sh sample --verbose         # Initialize with sample data and verbose output
./scripts/init_db.sh reset                    # Reset database (development only)
```

### `init_db.bat` (Windows)
Batch file wrapper for convenient database operations on Windows systems.

**Usage:**
```cmd
scripts\init_db.bat [COMMAND] [OPTIONS]
```

Same commands and options as the shell script version.

## Quick Start

### First Time Setup
1. Ensure your database is running and accessible
2. Update your `.env` file with the correct `DATABASE_URL`
3. Run the initialization script:

**Linux/macOS:**
```bash
./scripts/init_db.sh init
```

**Windows:**
```cmd
scripts\init_db.bat init
```

### Development Setup with Sample Data
For development environments, you can create sample data:

**Linux/macOS:**
```bash
./scripts/init_db.sh sample
```

**Windows:**
```cmd
scripts\init_db.bat sample
```

### Check Database Connection
To verify your database connection:

**Linux/macOS:**
```bash
./scripts/init_db.sh check
```

**Windows:**
```cmd
scripts\init_db.bat check
```

## Environment Variables

The scripts use the following environment variables from your `.env` file:

### Required
- `DATABASE_URL`: PostgreSQL connection string

### Optional Database Configuration
- `DATABASE_POOL_SIZE`: Connection pool size (default: 20)
- `DATABASE_MAX_OVERFLOW`: Max overflow connections (default: 30)
- `DATABASE_POOL_TIMEOUT`: Pool timeout in seconds (default: 30)
- `DATABASE_POOL_RECYCLE`: Connection recycle time in seconds (default: 3600)
- `DATABASE_POOL_PRE_PING`: Enable pre-ping (default: true)
- `DATABASE_ECHO`: Enable SQL query logging (default: false)
- `DATABASE_SSL_MODE`: PostgreSQL SSL mode (default: prefer)
- `DATABASE_CONNECT_TIMEOUT`: Connection timeout in seconds (default: 10)
- `DATABASE_COMMAND_TIMEOUT`: Command timeout in seconds (default: 60)

## Database Migrations

The scripts use Alembic for database migrations. Migration files are located in the `alembic/versions/` directory.

### Creating New Migrations
```bash
cd fintech_backend
alembic revision --autogenerate -m "Description of changes"
```

### Running Migrations
```bash
cd fintech_backend
alembic upgrade head
```

### Migration History
```bash
cd fintech_backend
alembic history
```

## Troubleshooting

### Common Issues

1. **Database Connection Failed**
   - Verify your `DATABASE_URL` in the `.env` file
   - Ensure the database server is running
   - Check network connectivity and firewall settings

2. **Permission Denied (Linux/macOS)**
   ```bash
   chmod +x scripts/init_db.sh
   ```

3. **Python Not Found**
   - Ensure Python is installed and in your PATH
   - For virtual environments, activate the environment first

4. **Alembic Command Not Found**
   - Ensure alembic is installed: `pip install alembic`
   - Check if you're in the correct directory

### Logging
Use the `--verbose` flag for detailed logging output to help diagnose issues.

## Safety Notes

- **NEVER** run `--force-reset` or the `reset` command in production
- Always backup your database before running reset operations
- The sample data creation is intended for development environments only
- Review migration files before applying them to production databases

## Support

For issues related to database setup or these scripts, please check:
1. The application logs for detailed error messages
2. Database server logs
3. Network connectivity between the application and database
4. Environment variable configuration
