-- Author: Claude Code (claude-opus-4-1-20250805)
-- Date: 2025-09-19
-- PURPOSE: PostgreSQL database initialization script for PlanExe - creates extensions and sets up database
-- SRP and DRY check: Pass - Single responsibility of database initialization

-- Create database if it doesn't exist (usually not needed in Docker)
-- CREATE DATABASE planexe;

-- Connect to the planexe database
\c planexe;

-- Create extensions that might be useful
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm"; -- For text search optimization

-- Grant permissions to the planexe_user
GRANT ALL PRIVILEGES ON DATABASE planexe TO planexe_user;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO planexe_user;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO planexe_user;

-- Create a function to update updated_at timestamps
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Note: SQLAlchemy will create the actual tables when the API starts up
-- This script just sets up the database foundation and extensions