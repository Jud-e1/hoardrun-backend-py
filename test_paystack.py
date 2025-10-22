#!/usr/bin/env python3
"""
Test script for Paystack integration.
"""
import asyncio
import os
import sys
from pathlib import Path

# Add the fintech_backend to the path
sys.path.insert(0, str(Path(__file__).parent / "fintech_backend"))

from app.external.paystack_client import PaystackClient
from app.config.settings import get_settings


async def test_paystack_integration():
    """Test Paystack integration with the provided test keys."""
    print("🏦 Testing Paystack Integration...")
    print("=" * 50)
    
    try:
        # Load settings
        settings = get_settings()
        
        print(f"✅ Environment: {settings.paystack_environment}")
        print(f"✅ Public Key: {settings.paystack_public_key[:20]}...")
        print(f"✅ Secret Key: {settings.paystack_secret_key[:20]}...")
        print()
        
        # Initialize Paystack client
        client = PaystackClient(
            public_key=settings.paystack_public_key,
            secret_key=settings.paystack_secret_key,
            environment=settings.paystack_environment,
            timeout=settings.paystack_timeout
        )
        
        print("🔧 Paystack client initialized successfully!")
        print()
        
        # Test 1: Initialize a test payment
        print("🧪 Test 1: Initialize Payment")
        print("-" * 30)
        
        test_email = "test@hoardrun.com"
        test_amount = 100  # 1 GHS in pesewas

        result = await client.initialize_transaction(
            email=test_email,
            amount=test_amount,
            currency="GHS",
            metadata={"test": True, "user_id": 123}
        )
        
        print(f"✅ Payment initialized successfully!")
        print(f"   Reference: {result['reference']}")
        print(f"   Authorization URL: {result['authorization_url']}")
        print(f"   Access Code: {result['access_code']}")
        print()
        
        # Test 2: Verify the payment (will show pending since not paid)
        print("🧪 Test 2: Verify Payment")
        print("-" * 30)
        
        verification = await client.verify_transaction(result['reference'])
        
        print(f"✅ Payment verification successful!")
        print(f"   Status: {verification['status']}")
        print(f"   Amount: {verification['amount']} kobo")
        print(f"   Currency: {verification['currency']}")
        print(f"   Channel: {verification.get('channel', 'N/A')}")
        print()
        
        # Test 3: List transactions
        print("🧪 Test 3: List Transactions")
        print("-" * 30)
        
        transactions = await client.list_transactions(per_page=5)
        
        print(f"✅ Transactions retrieved successfully!")
        print(f"   Total transactions: {len(transactions)}")
        if transactions:
            latest = transactions[0]
            print(f"   Latest transaction: {latest['reference']} - {latest['status']}")
        print()
        
        # Close the client
        await client.close()
        
        print("🎉 All tests passed! Paystack integration is working correctly.")
        print()
        print("📋 Next Steps:")
        print("1. Deploy your backend to Render with these environment variables")
        print("2. Test the API endpoints using the FastAPI docs")
        print("3. Integrate with your frontend application")
        print()
        print("🔗 API Endpoints Available:")
        print("   POST /api/v1/paystack/initialize")
        print("   GET  /api/v1/paystack/verify/{reference}")
        print("   GET  /api/v1/paystack/transactions")
        print("   POST /api/v1/paystack/webhook")
        print("   GET  /api/v1/paystack/config")
        print("   GET  /api/v1/paystack/health")
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        print()
        print("🔍 Troubleshooting:")
        print("1. Check that your Paystack keys are correct")
        print("2. Ensure you have internet connection")
        print("3. Verify that the pypaystack2 package is installed")
        return False
    
    return True


if __name__ == "__main__":
    # Run the test
    success = asyncio.run(test_paystack_integration())
    
    if success:
        print("\n✅ Integration test completed successfully!")
        exit(0)
    else:
        print("\n❌ Integration test failed!")
        exit(1)
