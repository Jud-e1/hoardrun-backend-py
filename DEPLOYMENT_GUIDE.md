# Deployment Guide for Hoardrun Backend

This guide covers deploying the Hoardrun fintech backend to Render.com.

## Prerequisites

1. A Render.com account
2. A GitHub repository with your code
3. A PostgreSQL database (can be created on Render)

## Deployment Options

### Option 1: Using render.yaml (Recommended)

The project includes a `render.yaml` file that defines the infrastructure as code.

1. **Push your code to GitHub**
2. **Connect to Render**:
   - Go to [Render Dashboard](https://dashboard.render.com)
   - Click "New" → "Blueprint"
   - Connect your GitHub repository
   - Render will automatically detect the `render.yaml` file

3. **Configure Environment Variables**:
   The render.yaml file includes most environment variables, but you may need to update:
   - `CORS_ORIGINS`: Add your frontend domain
   - `DATABASE_URL`: Will be automatically set from the database service
   - `SECRET_KEY`: Will be automatically generated

### Option 2: Manual Web Service Creation

1. **Create a PostgreSQL Database**:
   - Go to Render Dashboard
   - Click "New" → "PostgreSQL"
   - Choose a name (e.g., `hoardrun-db`)
   - Note the connection details

2. **Create a Web Service**:
   - Click "New" → "Web Service"
   - Connect your GitHub repository
   - Configure:
     - **Name**: `hoardrun-backend`
     - **Environment**: `Python 3`
     - **Build Command**: `cd fintech_backend && pip install -r requirements.txt && alembic upgrade head`
     - **Start Command**: `cd fintech_backend && uvicorn app.main:app --host 0.0.0.0 --port $PORT`

3. **Set Environment Variables**:
   ```
   ENVIRONMENT=production
   DEBUG=false
   DATABASE_URL=<your-postgres-connection-string>
   SECRET_KEY=<generate-a-secure-key>
   APP_NAME=Hoardrun Backend API
   LOG_LEVEL=INFO
   CORS_ORIGINS=["https://your-frontend-domain.com"]
   ```

### Option 3: Docker Deployment

The project includes a `Dockerfile` for containerized deployment.

1. **Enable Docker on Render**:
   - In your web service settings
   - Set **Environment** to `Docker`
   - Render will automatically use the Dockerfile

## Environment Variables Reference

### Required Variables
- `DATABASE_URL`: PostgreSQL connection string
- `SECRET_KEY`: JWT secret key (generate a secure random string)

### Optional Variables (with defaults)
- `ENVIRONMENT`: `production`
- `DEBUG`: `false`
- `LOG_LEVEL`: `INFO`
- `CORS_ORIGINS`: `["https://your-frontend-domain.com"]`
- `PORT`: Automatically set by Render

### Business Configuration
- `DEFAULT_CURRENCY`: `USD`
- `MAX_TRANSFER_AMOUNT`: `100000.0`
- `MIN_TRANSFER_AMOUNT`: `1.0`

## Database Setup

The deployment automatically runs database migrations using Alembic:
```bash
alembic upgrade head
```

This creates all necessary tables and applies any pending migrations.

## Health Checks

The application includes health check endpoints:
- `/health`: Basic health status
- `/`: Root endpoint with API information

## Monitoring and Logs

1. **View Logs**: Go to your service dashboard on Render
2. **Health Monitoring**: Render automatically monitors the `/health` endpoint
3. **Metrics**: Available in the Render dashboard

## Post-Deployment Verification

1. **Check Health Endpoint**:
   ```bash
   curl https://your-app-name.onrender.com/health
   ```

2. **Check API Documentation**:
   - Visit: `https://your-app-name.onrender.com/docs`
   - Interactive API documentation via Swagger UI

3. **Test Database Connection**:
   - The health endpoint includes database connectivity status

## Troubleshooting

### Common Issues

1. **Build Failures**:
   - Check that `requirements.txt` is in the `fintech_backend/` directory
   - Ensure all dependencies are properly specified

2. **Database Connection Issues**:
   - Verify `DATABASE_URL` environment variable
   - Check database service is running
   - Ensure database allows connections from your web service

3. **Migration Failures**:
   - Check Alembic configuration in `alembic/env.py`
   - Verify all models are imported in `app/database/models.py`

4. **Port Binding Issues**:
   - Ensure the app binds to `0.0.0.0:$PORT`
   - Render automatically sets the `PORT` environment variable

### Debug Steps

1. **Check Service Logs**:
   - Go to Render dashboard → Your service → Logs

2. **Verify Environment Variables**:
   - Check all required variables are set
   - Ensure no typos in variable names

3. **Test Locally**:
   ```bash
   cd fintech_backend
   pip install -r requirements.txt
   uvicorn app.main:app --reload
   ```

## Security Considerations

1. **Environment Variables**: Never commit sensitive data to version control
2. **CORS Configuration**: Restrict origins to your actual frontend domains
3. **Database Security**: Use strong passwords and restrict access
4. **HTTPS**: Render provides HTTPS by default
5. **Secret Key**: Generate a strong, unique secret key for JWT tokens

## Scaling

Render automatically handles:
- Load balancing
- SSL certificates
- Health checks
- Auto-scaling (on paid plans)

For high-traffic applications, consider:
- Upgrading to a paid plan for better performance
- Adding Redis for caching
- Database connection pooling optimization

## Support

- [Render Documentation](https://render.com/docs)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [Alembic Documentation](https://alembic.sqlalchemy.org/)
