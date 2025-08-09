#!/usr/bin/env python3
"""
Falcon Parse - Setup Test Script
Tests the basic functionality without requiring full setup
"""

import sys
import os
import asyncio
from pathlib import Path

# Add backend to Python path
backend_path = Path(__file__).parent / "backend"
sys.path.insert(0, str(backend_path))

async def test_basic_imports():
    """Test that all required modules can be imported"""
    try:
        print("🔍 Testing imports...")
        
        # Test FastAPI imports
        from fastapi import FastAPI
        print("✅ FastAPI imported successfully")
        
        # Test scraping imports
        from bs4 import BeautifulSoup
        print("✅ BeautifulSoup imported successfully")
        
        # Test data processing
        import pandas as pd
        print("✅ Pandas imported successfully")
        
        # Test models
        from models.scrape_models import ScrapeRequest, ScrapeResult
        print("✅ Pydantic models imported successfully")
        
        return True
        
    except ImportError as e:
        print(f"❌ Import failed: {e}")
        return False

async def test_services():
    """Test service initialization"""
    try:
        print("\n🔧 Testing services...")
        
        # Test data processor (doesn't need API key)
        from services.data_processor import DataProcessor
        processor = DataProcessor()
        print("✅ DataProcessor initialized")
        
        # Test basic data processing
        test_data = [
            {"name": "Test Item", "price": "19.99", "available": "yes"},
            {"name": "Another Item", "price": "29.99", "available": "no"}
        ]
        
        result = processor.process_data(test_data)
        print(f"✅ Data processing test: {len(result['data'])} items processed")
        
        return True
        
    except Exception as e:
        print(f"❌ Service test failed: {e}")
        return False

async def test_gemini_setup():
    """Test Gemini client setup (without API call)"""
    try:
        print("\n🤖 Testing Gemini setup...")
        
        # Check if API key is set
        from dotenv import load_dotenv
        load_dotenv()
        
        api_key = os.getenv('GEMINI_API_KEY')
        if not api_key or api_key == 'your_gemini_api_key_here':
            print("⚠️  Gemini API key not configured")
            return False
        
        print("✅ Gemini API key found")
        
        # Test basic import (without initialization)
        import google.generativeai as genai
        print("✅ Gemini library imported successfully")
        
        return True
        
    except Exception as e:
        print(f"❌ Gemini setup test failed: {e}")
        return False

async def main():
    """Run all tests"""
    print("🦅 Falcon Parse - Setup Test\n")
    
    tests = [
        test_basic_imports(),
        test_services(),
        test_gemini_setup()
    ]
    
    results = await asyncio.gather(*tests, return_exceptions=True)
    
    success_count = sum(1 for result in results if result is True)
    total_tests = len(results)
    
    print(f"\n📊 Test Results: {success_count}/{total_tests} passed")
    
    if success_count == total_tests:
        print("🎉 All tests passed! Falcon Parse is ready to run.")
        print("\nNext steps:")
        print("1. Make sure your .env file has GEMINI_API_KEY set")
        print("2. Run: ./start.sh")
        print("3. Open: http://localhost:3010")
        return True
    else:
        print("❌ Some tests failed. Please check the errors above.")
        return False

if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)