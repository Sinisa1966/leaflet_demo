#!/usr/bin/env python3
"""Test server endpoint"""
import sys
import urllib.request
import urllib.error
import json

def test_endpoint(path):
    url = f"http://localhost:5010{path}"
    print(f"Testing: {url}")
    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=5) as resp:
            print(f"Status: {resp.status}")
            body = resp.read().decode('utf-8')
            print(f"Response: {body}")
            return True
    except urllib.error.HTTPError as e:
        print(f"HTTP Error {e.code}: {e.read().decode('utf-8')}")
        return False
    except Exception as e:
        print(f"Error: {e}")
        return False

if __name__ == "__main__":
    print("Testing /ndre_zones endpoint...")
    test_endpoint("/ndre_zones?parcel=1427/2&layer=kovin_dkp_pg")
    print("\nTesting /run endpoint (should work)...")
    test_endpoint("/run?parcel=1427/2&layer=kovin_dkp_pg")
