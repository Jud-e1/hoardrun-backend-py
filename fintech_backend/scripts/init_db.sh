#!/bin/bash

# Database initialization script wrapper
# This script provides convenient shortcuts for common database operations

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

echo -e "${BLUE}HoardRun Fintech Backend - Database Initialization${NC}"
echo "=================================================="

# Function to print colored output
print_status() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if Python is available
if ! command -v python &> /dev/null; then
    print_error "Python is not installed or not in PATH"
    exit 1
fi

# Change to project directory
cd "$PROJECT_DIR"

# Function to show usage
show_usage() {
    echo "Usage: $0 [COMMAND] [OPTIONS]"
    echo ""
    echo "Commands:"
    echo "  check       - Check database connection only"
    echo "  init        - Initialize database with migrations"
    echo "  reset       - Reset database (DANGEROUS - development only)"
    echo "  sample      - Initialize database and create sample data"
    echo "  migrate     - Run migrations only"
    echo ""
    echo "Options:"
    echo "  --verbose   - Enable verbose output"
    echo ""
    echo "Examples:"
    echo "  $0 check                    # Check database connection"
    echo "  $0 init                     # Initialize database"
    echo "  $0 sample --verbose         # Initialize with sample data and verbose output"
    echo "  $0 reset                    # Reset database (development only)"
}

# Parse command line arguments
COMMAND=""
VERBOSE=""

while [[ $# -gt 0 ]]; do
    case $1 in
        check|init|reset|sample|migrate)
            COMMAND="$1"
            shift
            ;;
        --verbose)
            VERBOSE="--verbose"
            shift
            ;;
        -h|--help)
            show_usage
            exit 0
            ;;
        *)
            print_error "Unknown option: $1"
            show_usage
            exit 1
            ;;
    esac
done

# If no command specified, show usage
if [[ -z "$COMMAND" ]]; then
    show_usage
    exit 1
fi

# Execute the appropriate command
case $COMMAND in
    check)
        print_status "Checking database connection..."
        python scripts/init_database.py --check-only $VERBOSE
        ;;
    init)
        print_status "Initializing database..."
        python scripts/init_database.py $VERBOSE
        ;;
    reset)
        print_warning "This will reset the database and delete all data!"
        python scripts/init_database.py --force-reset $VERBOSE
        ;;
    sample)
        print_status "Initializing database with sample data..."
        python scripts/init_database.py --create-sample-data $VERBOSE
        ;;
    migrate)
        print_status "Running database migrations..."
        cd "$PROJECT_DIR"
        alembic upgrade head
        ;;
    *)
        print_error "Unknown command: $COMMAND"
        show_usage
        exit 1
        ;;
esac

print_status "Operation completed successfully!"
