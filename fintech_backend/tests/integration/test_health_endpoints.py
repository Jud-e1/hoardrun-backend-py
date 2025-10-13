"""
Integration tests for health check endpoints.
"""

import pytest
from unittest.mock import patch, MagicMock


class TestHealthEndpoints:
    """Test health check endpoints."""
    
    def test_basic_health_check(self, client):
        """Test basic health check endpoint."""
        response = client.get("/api/health/")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "timestamp" in data
    
    def test_detailed_health_check(self, client):
        """Test detailed health check endpoint."""
        response = client.get("/api/health/detailed")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["service"] == "fintech-backend"
        assert "system" in data
        assert "dependencies" in data
        assert "timestamp" in data
        
        # Check system information
        system = data["system"]
        assert "python_version" in system
        assert "memory" in system
        assert "disk" in system
        
        # Check dependencies
        dependencies = data["dependencies"]
        assert "database" in dependencies
    
    def test_database_health_check_success(self, client):
        """Test database health check endpoint when database is healthy."""
        with patch('app.database.get_database_info') as mock_get_db_info:
            mock_get_db_info.return_value = {
                "database_url": "sqlite:///test.db",
                "database_version": "SQLite 3.x",
                "connection_healthy": True,
                "pool_info": {
                    "pool_size": 5,
                    "checked_in": 0,
                    "checked_out": 1,
                    "overflow": 0
                }
            }
            
            response = client.get("/api/health/database")
            
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "healthy"
            assert "database" in data
            assert data["database"]["connection_healthy"] is True
    
    def test_database_health_check_failure(self, client):
        """Test database health check endpoint when database is unhealthy."""
        with patch('app.database.get_database_info') as mock_get_db_info:
            mock_get_db_info.return_value = {
                "database_url": "sqlite:///test.db",
                "error": "Connection failed",
                "connection_healthy": False
            }
            
            response = client.get("/api/health/database")
            
            assert response.status_code == 503
            data = response.json()
            assert data["status"] == "unhealthy"
            assert "database" in data
            assert data["database"]["connection_healthy"] is False
    
    def test_database_health_check_exception(self, client):
        """Test database health check endpoint when an exception occurs."""
        with patch('app.database.get_database_info') as mock_get_db_info:
            mock_get_db_info.side_effect = Exception("Database connection error")
            
            response = client.get("/api/health/database")
            
            assert response.status_code == 503
            data = response.json()
            assert data["status"] == "unhealthy"
            assert "error" in data
    
    def test_readiness_check_success(self, client):
        """Test readiness check endpoint when service is ready."""
        with patch('app.database.check_database_connection') as mock_check_db:
            mock_check_db.return_value = True
            
            response = client.get("/api/health/readiness")
            
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "ready"
            assert "checks" in data
            assert data["checks"]["database"] == "healthy"
    
    def test_readiness_check_failure(self, client):
        """Test readiness check endpoint when service is not ready."""
        with patch('app.database.check_database_connection') as mock_check_db:
            mock_check_db.return_value = False
            
            response = client.get("/api/health/readiness")
            
            assert response.status_code == 503
            data = response.json()
            assert data["status"] == "not_ready"
            assert "checks" in data
            assert data["checks"]["database"] == "unhealthy"
    
    def test_readiness_check_exception(self, client):
        """Test readiness check endpoint when an exception occurs."""
        with patch('app.database.check_database_connection') as mock_check_db:
            mock_check_db.side_effect = Exception("Database error")
            
            response = client.get("/api/health/readiness")
            
            assert response.status_code == 503
            data = response.json()
            assert data["status"] == "not_ready"
            assert "error" in data
    
    def test_liveness_check(self, client):
        """Test liveness check endpoint."""
        response = client.get("/api/health/liveness")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "alive"
        assert "timestamp" in data
        assert "uptime" in data
    
    def test_liveness_check_exception(self, client):
        """Test liveness check endpoint when an exception occurs."""
        # This is harder to test since liveness check is very simple
        # But we can test the exception handling structure
        with patch('app.api.health.datetime') as mock_datetime:
            mock_datetime.utcnow.side_effect = Exception("Time error")
            
            response = client.get("/api/health/liveness")
            
            assert response.status_code == 503
            data = response.json()
            assert data["status"] == "dead"
            assert "error" in data


class TestHealthEndpointsIntegration:
    """Integration tests for health endpoints with real database."""
    
    def test_health_endpoints_with_real_database(self, client, test_db):
        """Test health endpoints with actual database connection."""
        # Test basic health
        response = client.get("/api/health/")
        assert response.status_code == 200
        
        # Test detailed health
        response = client.get("/api/health/detailed")
        assert response.status_code == 200
        data = response.json()
        assert data["dependencies"]["database"] is True  # Should be True with test DB
        
        # Test database health
        response = client.get("/api/health/database")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        
        # Test readiness
        response = client.get("/api/health/readiness")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ready"
        
        # Test liveness
        response = client.get("/api/health/liveness")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "alive"
    
    def test_health_endpoint_response_structure(self, client):
        """Test that health endpoints return properly structured responses."""
        endpoints = [
            "/api/health/",
            "/api/health/detailed",
            "/api/health/database",
            "/api/health/readiness",
            "/api/health/liveness"
        ]
        
        for endpoint in endpoints:
            response = client.get(endpoint)
            assert response.status_code in [200, 503]  # Either healthy or unhealthy
            
            data = response.json()
            assert "status" in data
            assert "timestamp" in data
            
            # Verify timestamp format
            timestamp = data["timestamp"]
            assert isinstance(timestamp, str)
            # Should be ISO format
            assert "T" in timestamp or " " in timestamp
    
    def test_health_endpoints_cors(self, client):
        """Test that health endpoints support CORS."""
        response = client.options("/api/health/")
        # Should not return 405 Method Not Allowed
        assert response.status_code != 405
        
        # Test with actual request
        response = client.get("/api/health/")
        assert response.status_code == 200
    
    def test_health_endpoints_performance(self, client):
        """Test that health endpoints respond quickly."""
        import time
        
        endpoints = [
            "/api/health/",
            "/api/health/liveness",
            "/api/health/readiness"
        ]
        
        for endpoint in endpoints:
            start_time = time.time()
            response = client.get(endpoint)
            end_time = time.time()
            
            # Health checks should be fast (under 1 second)
            assert (end_time - start_time) < 1.0
            assert response.status_code in [200, 503]


class TestHealthEndpointsErrorHandling:
    """Test error handling in health endpoints."""
    
    def test_detailed_health_check_system_error(self, client):
        """Test detailed health check when system info fails."""
        with patch('psutil.virtual_memory') as mock_memory:
            mock_memory.side_effect = Exception("Memory error")
            
            response = client.get("/api/health/detailed")
            
            assert response.status_code == 503
            data = response.json()
            assert data["status"] == "unhealthy"
            assert "error" in data
    
    def test_health_endpoints_with_invalid_methods(self, client):
        """Test health endpoints with invalid HTTP methods."""
        endpoints = [
            "/api/health/",
            "/api/health/detailed",
            "/api/health/database",
            "/api/health/readiness",
            "/api/health/liveness"
        ]
        
        for endpoint in endpoints:
            # POST should not be allowed
            response = client.post(endpoint)
            assert response.status_code == 405
            
            # PUT should not be allowed
            response = client.put(endpoint)
            assert response.status_code == 405
            
            # DELETE should not be allowed
            response = client.delete(endpoint)
            assert response.status_code == 405
    
    def test_health_endpoints_content_type(self, client):
        """Test that health endpoints return JSON content type."""
        endpoints = [
            "/api/health/",
            "/api/health/detailed",
            "/api/health/database",
            "/api/health/readiness",
            "/api/health/liveness"
        ]
        
        for endpoint in endpoints:
            response = client.get(endpoint)
            assert response.status_code in [200, 503]
            assert "application/json" in response.headers.get("content-type", "")
