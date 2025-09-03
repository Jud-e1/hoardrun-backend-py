# Fintech Backend API

A comprehensive Python FastAPI backend service for fintech applications providing REST API endpoints for financial operations including dashboard analytics, card management, account operations, transactions, money transfers, investments, and savings management.

## Features

- **Dashboard & Analytics** - Financial summaries and spending analytics
- **Card Management** - Card operations, limits, and freeze/unfreeze functionality
- **Account Management** - Account balances, statements, and financial overview
- **Transaction Management** - Transaction history, search, and categorization
- **Money Transfers** - Transfer initiation, status tracking, and beneficiary management
- **Send/Receive Money** - Peer-to-peer money operations with quotes
- **Investment Portfolio** - Portfolio management, stock quotes, and market data
- **Savings Management** - Savings goals, automation, and growth calculations
- **Settings & Profile** - User preferences and security settings

## Project Structure

```
fintech_backend/
├── app/
│   ├── main.py                 # FastAPI application entry point
│   ├── config/                 # Configuration management
│   ├── core/                   # Core utilities and middleware
│   ├── models/                 # Pydantic data models
│   ├── services/               # Business logic services
│   ├── repositories/           # Data access layer
│   ├── external/               # External service clients
│   ├── api/                    # API route handlers
│   └── utils/                  # Utility functions
├── tests/                      # Test suites
├── requirements.txt            # Production dependencies
├── requirements-dev.txt        # Development dependencies
└── .env.example               # Environment configuration template
```

## Quick Start

1. **Clone and navigate to the project:**
   ```bash
   cd fintech_backend
   ```

2. **Create a virtual environment:**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Set up environment variables:**
   ```bash
   cp .env.example .env
   # Edit .env with your configuration
   ```

5. **Run the application:**
   ```bash
   cd app
   python main.py
   ```

   Or using uvicorn directly:
   ```bash
   uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
   ```

6. **Access the API:**
   - API Documentation: http://localhost:8000/docs
   - Alternative Docs: http://localhost:8000/redoc
   - Health Check: http://localhost:8000/health

## Development

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=app

# Run specific test file
pytest tests/unit/test_services.py
```

### Code Quality

```bash
# Format code
black app/ tests/

# Sort imports
isort app/ tests/

# Lint code
flake8 app/ tests/

# Type checking
mypy app/
```

## API Endpoints

### Health Checks
- `GET /` - Root endpoint with API information
- `GET /health` - Comprehensive health check
- `GET /health/ready` - Readiness probe
- `GET /health/live` - Liveness probe

### Core Features (To be implemented)
- `GET /api/v1/dashboard/*` - Dashboard and analytics
- `GET /api/v1/cards/*` - Card management
- `GET /api/v1/accounts/*` - Account operations
- `GET /api/v1/transactions/*` - Transaction management
- `POST /api/v1/transfers/*` - Money transfers
- `POST /api/v1/send-receive/*` - P2P money operations
- `GET /api/v1/investments/*` - Investment portfolio
- `GET /api/v1/savings/*` - Savings management
- `GET /api/v1/settings/*` - User settings

## Architecture

The application follows a layered architecture with:

- **Presentation Layer** - FastAPI routers and endpoint handlers
- **Business Logic Layer** - Service classes with domain logic
- **Data Access Layer** - Repository pattern with mock implementations
- **External Integration Layer** - Mock external service clients
- **Cross-Cutting Concerns** - Middleware, logging, configuration

## Technology Stack

- **FastAPI** - Modern, fast web framework for building APIs
- **Pydantic** - Data validation and settings management
- **Uvicorn** - ASGI server for running the application
- **Pytest** - Testing framework
- **Structlog** - Structured logging
- **HTTPX** - HTTP client for external services

## License

This project is for educational and demonstration purposes.