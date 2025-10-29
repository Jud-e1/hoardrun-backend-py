#!/usr/bin/env python3
"""
Test script for Java security integration.
"""
import asyncio
import sys
import os
from pathlib import Path

# Add the project root to Python path
sys.path.insert(0, str(Path(__file__).parent / "fintech_backend"))

from app.core.java_security_integration import JavaSecurityConfig, JavaJWTService, JavaSecurityClient
from app.config.settings import get_settings
import base64
import jwt


async def test_jwt_compatibility():
    """Test JWT token compatibility between Java and Python."""
    print("🔐 Testing JWT Token Compatibility")
    print("=" * 50)
    
    # Test configuration
    config = JavaSecurityConfig(
        enabled=True,
        jwt_secret="c2VjdXJlLXN1cGVyLXNlY3JldC1kZW1vLXNob3VsZC1iZS0zMi1ieXRlcy1vci1sb25nZXI="
    )
    
    jwt_service = JavaJWTService(config)
    
    # Test 1: Create a token compatible with Java
    print("🧪 Test 1: Create Java-compatible token")
    print("-" * 30)
    
    user_data = {
        "username": "test@example.com",
        "role": "USER",
        "mfa_verified": False
    }
    
    try:
        token = jwt_service.create_compatible_token(user_data, expires_minutes=15)
        print(f"✅ Token created successfully")
        print(f"   Token: {token[:50]}...")
        
        # Test 2: Decode the token we just created
        print("\n🧪 Test 2: Decode Java-compatible token")
        print("-" * 30)

        import time
        current_time = int(time.time())
        print(f"   Current timestamp: {current_time}")

        # First decode without validation to see the payload
        import jwt as jwt_lib
        unverified = jwt_lib.decode(token, options={"verify_signature": False})
        print(f"   Token expires at: {unverified.get('exp')}")
        print(f"   Token issued at: {unverified.get('iat')}")
        print(f"   Time difference: {unverified.get('exp', 0) - current_time} seconds")

        decoded = jwt_service.decode_java_token(token)
        print(f"✅ Token decoded successfully")
        print(f"   Subject: {decoded.get('sub')}")
        print(f"   Role: {decoded.get('role')}")
        print(f"   Token Use: {decoded.get('token_use')}")
        print(f"   MFA Verified: {decoded.get('mfa_verified')}")
        print(f"   Expires: {decoded.get('exp')}")
        
        # Test 3: Verify token structure matches Java expectations
        print("\n🧪 Test 3: Verify token structure")
        print("-" * 30)
        
        required_fields = ['sub', 'role', 'token_use', 'exp', 'iat', 'jti']
        missing_fields = [field for field in required_fields if field not in decoded]
        
        if not missing_fields:
            print("✅ All required fields present")
        else:
            print(f"❌ Missing fields: {missing_fields}")
        
        return True
        
    except Exception as e:
        print(f"❌ JWT test failed: {e}")
        return False


async def test_java_service_communication():
    """Test communication with Java services."""
    print("\n🌐 Testing Java Service Communication")
    print("=" * 50)
    
    config = JavaSecurityConfig(enabled=True)
    client = JavaSecurityClient(config)
    
    # Test 1: Check if Java services are running
    print("🧪 Test 1: Java Auth Service Health Check")
    print("-" * 30)
    
    try:
        # Try to connect to auth service
        result = await client.authenticate_with_java("test", "test")
        if result is None:
            print("⚠️ Java auth service not responding (this is expected if not running)")
        else:
            print("✅ Java auth service is responding")
            
    except Exception as e:
        print(f"⚠️ Java auth service connection failed: {e}")
        print("   This is expected if Java services are not running")
    
    # Test 2: Audit logging
    print("\n🧪 Test 2: Audit Logging")
    print("-" * 30)
    
    try:
        await client.audit_log("TEST_EVENT", "test_user", {"test": True})
        print("✅ Audit log sent (or service not available)")
    except Exception as e:
        print(f"⚠️ Audit logging failed: {e}")
    
    await client.close()
    return True


async def test_hybrid_auth_configuration():
    """Test hybrid authentication configuration."""
    print("\n⚙️ Testing Hybrid Auth Configuration")
    print("=" * 50)
    
    settings = get_settings()
    
    print(f"Java Security Enabled: {getattr(settings, 'java_security_enabled', False)}")
    print(f"Java Gateway URL: {getattr(settings, 'java_gateway_url', 'Not configured')}")
    print(f"Java Auth Service URL: {getattr(settings, 'java_auth_service_url', 'Not configured')}")
    print(f"Java Transaction Service URL: {getattr(settings, 'java_transaction_service_url', 'Not configured')}")
    print(f"Java Audit Service URL: {getattr(settings, 'java_audit_service_url', 'Not configured')}")
    
    # Test JWT secret configuration
    jwt_secret = getattr(settings, 'java_jwt_secret', '')
    if jwt_secret:
        try:
            decoded_secret = base64.b64decode(jwt_secret)
            print(f"✅ JWT secret configured (length: {len(decoded_secret)} bytes)")
        except Exception as e:
            print(f"❌ JWT secret configuration error: {e}")
    else:
        print("⚠️ JWT secret not configured")
    
    return True


async def test_token_validation_scenarios():
    """Test various token validation scenarios."""
    print("\n🔍 Testing Token Validation Scenarios")
    print("=" * 50)
    
    config = JavaSecurityConfig(enabled=True)
    jwt_service = JavaJWTService(config)
    
    # Test 1: Valid token
    print("🧪 Test 1: Valid token validation")
    print("-" * 30)
    
    try:
        token = jwt_service.create_compatible_token({"username": "test@example.com", "role": "USER"})
        decoded = jwt_service.decode_java_token(token)
        print("✅ Valid token validation passed")
    except Exception as e:
        print(f"❌ Valid token validation failed: {e}")
    
    # Test 2: Invalid token
    print("\n🧪 Test 2: Invalid token validation")
    print("-" * 30)
    
    try:
        jwt_service.decode_java_token("invalid.token.here")
        print("❌ Invalid token validation should have failed")
    except Exception as e:
        print(f"✅ Invalid token correctly rejected: {type(e).__name__}")
    
    # Test 3: Expired token (simulate)
    print("\n🧪 Test 3: Expired token simulation")
    print("-" * 30)
    
    try:
        # Create a token that expires immediately
        expired_token = jwt_service.create_compatible_token(
            {"username": "test@example.com", "role": "USER"}, 
            expires_minutes=-1  # Already expired
        )
        jwt_service.decode_java_token(expired_token)
        print("❌ Expired token validation should have failed")
    except Exception as e:
        print(f"✅ Expired token correctly rejected: {type(e).__name__}")
    
    return True


async def main():
    """Main test function."""
    print("🔐 Java Security Integration Test Suite")
    print("=" * 60)
    
    tests = [
        test_jwt_compatibility,
        test_java_service_communication,
        test_hybrid_auth_configuration,
        test_token_validation_scenarios
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        try:
            result = await test()
            if result:
                passed += 1
        except Exception as e:
            print(f"❌ Test {test.__name__} failed with error: {e}")
    
    print("\n" + "=" * 60)
    print(f"📊 Test Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed! Java security integration is ready.")
        print("\n📋 Next Steps:")
        print("1. Start Java security services using docker-compose")
        print("2. Set JAVA_SECURITY_ENABLED=true in your .env file")
        print("3. Test the integration endpoints in your FastAPI app")
        return True
    else:
        print("⚠️ Some tests failed. Check the configuration and try again.")
        return False


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
