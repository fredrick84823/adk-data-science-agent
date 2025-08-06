#!/usr/bin/env python3
"""Test script for environment detection functionality."""

import sys
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Add the current directory to path so we can import utils
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'data_science'))

# Import our utility functions
from utils.utils import is_cloud_run_environment, get_credentials_path

def test_environment_detection():
    """Test the environment detection functions."""
    
    print("=== Local Environment Test ===")
    print(f"K_SERVICE env var: {os.getenv('K_SERVICE')}")
    print(f"K_REVISION env var: {os.getenv('K_REVISION')}")
    print(f"/workspace exists: {os.path.exists('/workspace')}")
    print(f"Is Cloud Run Environment: {is_cloud_run_environment()}")
    
    print("\n=== Local Credentials Path Test ===")
    print(f"GOOGLE_APPLICATION_CREDENTIALS: {os.getenv('GOOGLE_APPLICATION_CREDENTIALS')}")
    print(f"Resolved Credentials Path: {get_credentials_path()}")
    
    # Test file existence
    cred_path = get_credentials_path()
    if cred_path:
        print(f"Credentials file exists: {os.path.exists(cred_path)}")
    else:
        print("No credentials path configured")
    
    print("\n=== Simulated Cloud Run Environment Test ===")
    # Temporarily set Cloud Run environment variable
    os.environ['K_SERVICE'] = 'test-service'
    print(f"K_SERVICE env var: {os.getenv('K_SERVICE')}")
    print(f"Is Cloud Run Environment: {is_cloud_run_environment()}")
    print(f"Simulated Cloud Run Credentials Path: {get_credentials_path()}")
    
    # Clean up
    del os.environ['K_SERVICE']

if __name__ == "__main__":
    test_environment_detection()