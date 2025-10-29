-- Database initialization script for hybrid Python + Java architecture
-- Creates separate schemas for Python and Java services

-- Create schemas
CREATE SCHEMA IF NOT EXISTS python_backend;
CREATE SCHEMA IF NOT EXISTS java_auth;
CREATE SCHEMA IF NOT EXISTS java_transaction;
CREATE SCHEMA IF NOT EXISTS java_audit;

-- Create users for different services
CREATE USER IF NOT EXISTS python_user WITH PASSWORD 'python_password';
CREATE USER IF NOT EXISTS auth_user WITH PASSWORD 'auth_password';
CREATE USER IF NOT EXISTS transaction_user WITH PASSWORD 'transaction_password';
CREATE USER IF NOT EXISTS audit_user WITH PASSWORD 'audit_password';

-- Grant permissions
GRANT ALL PRIVILEGES ON SCHEMA python_backend TO python_user;
GRANT ALL PRIVILEGES ON SCHEMA java_auth TO auth_user;
GRANT ALL PRIVILEGES ON SCHEMA java_transaction TO transaction_user;
GRANT ALL PRIVILEGES ON SCHEMA java_audit TO audit_user;

-- Allow cross-schema access for integration
GRANT USAGE ON SCHEMA java_auth TO python_user;
GRANT SELECT ON ALL TABLES IN SCHEMA java_auth TO python_user;
GRANT USAGE ON SCHEMA python_backend TO auth_user;
GRANT SELECT ON ALL TABLES IN SCHEMA python_backend TO auth_user;

-- Set default search paths
ALTER USER python_user SET search_path = python_backend, public;
ALTER USER auth_user SET search_path = java_auth, public;
ALTER USER transaction_user SET search_path = java_transaction, public;
ALTER USER audit_user SET search_path = java_audit, public;
