#!/usr/bin/env python3
"""
Simple test script to verify Paystack API keys.
"""
import asyncio
import httpx
import json


async def test_paystack_keys():
    """Test Paystack keys with a simple API call."""
    
    # Your test keys
    secret_key = "sk_test_79e3ff2db36022a047a1c24e1b544c9eea41e25a"
    
    print("🔑 Testing Paystack API Keys...")
    print("=" * 40)
    
    # Test 1: Simple API call to list transactions (should work even if empty)
    print("🧪 Test 1: List Transactions (Simple API Test)")
    print("-" * 40)
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                "https://api.paystack.co/transaction",
                headers={
                    "Authorization": f"Bearer {secret_key}",
                    "Content-Type": "application/json"
                },
                params={"perPage": 1}
            )
            
            print(f"Status Code: {response.status_code}")

            if response.status_code == 200:
                print("✅ API keys are valid!")
                data = response.json()
                print(f"✅ Response status: {data.get('status')}")
                print(f"✅ Message: {data.get('message')}")

                # Check what currencies are being used
                transactions = data.get('data', [])
                if transactions:
                    currencies = set()
                    for txn in transactions[:5]:  # Check first 5 transactions
                        currencies.add(txn.get('currency', 'Unknown'))
                    print(f"✅ Currencies found in existing transactions: {list(currencies)}")
                else:
                    print("ℹ️ No existing transactions found")
            else:
                print(f"❌ API call failed: {response.status_code}")
                print(f"❌ Response: {response.text}")
                
    except Exception as e:
        print(f"❌ Error: {e}")
    
    print()
    
    # Test 2: Initialize transaction
    print("🧪 Test 2: Initialize Transaction")
    print("-" * 40)
    
    try:
        payload = {
            "email": "test@example.com",
            "amount": 100,  # 1 GHS in pesewas
            "currency": "GHS"
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://api.paystack.co/transaction/initialize",
                headers={
                    "Authorization": f"Bearer {secret_key}",
                    "Content-Type": "application/json"
                },
                json=payload
            )
            
            print(f"Status Code: {response.status_code}")
            print(f"Response: {response.text[:300]}...")
            
            if response.status_code == 200:
                print("✅ Transaction initialization successful!")
                data = response.json()
                if data.get('status'):
                    print(f"✅ Authorization URL: {data['data']['authorization_url']}")
                    print(f"✅ Reference: {data['data']['reference']}")
                else:
                    print(f"❌ API returned error: {data.get('message')}")
            else:
                print(f"❌ Transaction initialization failed: {response.status_code}")
                print(f"❌ Response: {response.text}")
                
    except Exception as e:
        print(f"❌ Error: {e}")


if __name__ == "__main__":
    asyncio.run(test_paystack_keys())
