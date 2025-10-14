#!/usr/bin/env python3
"""
Test script to verify login functionality and database connection.
"""

import os
import sys
import json
import requests
import time

# Add the fintech_backend directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'fintech_backend'))

def test_backend_health():
    """Test backend health endpoints."""
    base_url = "http://localhost:8000"
    
    print("🔍 Testing Backend Health Endpoints")
    print("=" * 50)
    
    endpoints = [
        ("/api/health/", "Basic Health Check"),
        ("/api/health/database", "Database Health Check"),
        ("/api/health/detailed", "Detailed Health Check"),
    ]
    
    for endpoint, name in endpoints:
        try:
            print(f"\n📡 Testing {name}...")
            response = requests.get(f"{base_url}{endpoint}", timeout=10)
            
            print(f"   Status Code: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                print(f"   ✅ {name}: {data.get('status', 'unknown')}")
                if 'timestamp' in data:
                    print(f"   🕒 Timestamp: {data['timestamp']}")
            else:
                print(f"   ❌ {name} failed")
                try:
                    error_data = response.json()
                    print(f"   Error: {error_data}")
                except:
                    print(f"   Error: {response.text}")
                    
        except requests.exceptions.ConnectionError:
            print(f"   ❌ Connection failed - is the server running?")
        except Exception as e:
            print(f"   ❌ Error: {e}")

def test_auth_endpoints():
    """Test authentication endpoints."""
    base_url = "http://localhost:8000"
    
    print("\n🔐 Testing Authentication Endpoints")
    print("=" * 50)
    
    # Test registration first
    print("\n📝 Testing User Registration...")
    register_data = {
        "email": "test@example.com",
        "password": "TestPassword123!",
        "first_name": "Test",
        "last_name": "User",
        "terms_accepted": True
    }
    
    try:
        response = requests.post(
            f"{base_url}/api/v1/auth/register",
            json=register_data,
            timeout=10
        )
        print(f"   Registration Status: {response.status_code}")
        
        if response.status_code in [200, 201]:
            print("   ✅ Registration successful")
        elif response.status_code == 400:
            error_data = response.json()
            if "already exists" in str(error_data):
                print("   ℹ️  User already exists (expected)")
            else:
                print(f"   ❌ Registration error: {error_data}")
        else:
            print(f"   ❌ Registration failed: {response.text}")
            
    except Exception as e:
        print(f"   ❌ Registration error: {e}")
    
    # Test login
    print("\n🔑 Testing User Login...")
    login_data = {
        "email": "test@example.com",
        "password": "TestPassword123!"
    }
    
    try:
        response = requests.post(
            f"{base_url}/api/v1/auth/login",
            json=login_data,
            timeout=10
        )
        print(f"   Login Status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print("   ✅ Login successful")
            if 'data' in data and 'access_token' in data['data']:
                print("   🎫 Access token received")
            else:
                print("   ⚠️  No access token in response")
                print(f"   Response: {data}")
        else:
            print(f"   ❌ Login failed")
            try:
                error_data = response.json()
                print(f"   Error: {error_data}")
            except:
                print(f"   Error: {response.text}")
                
    except Exception as e:
        print(f"   ❌ Login error: {e}")

def main():
    """Run all tests."""
    print("🧪 HoardRun Backend Test Suite")
    print("=" * 50)
    
    # Wait a moment for server to be ready
    print("⏳ Waiting for server to be ready...")
    time.sleep(2)
    
    # Test health endpoints
    test_backend_health()
    
    # Test auth endpoints
    test_auth_endpoints()
    
    print("\n" + "=" * 50)
    print("✅ Test suite completed!")
    print("\n💡 Tips:")
    print("   - If health checks fail, check if the server is running")
    print("   - If database errors occur, check the DATABASE_URL setting")
    print("   - Check server logs for detailed error information")

if __name__ == "__main__":
    main()
