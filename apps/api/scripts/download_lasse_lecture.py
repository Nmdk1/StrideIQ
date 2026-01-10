#!/usr/bin/env python3
"""Download Lasse Storgaard Jacobsen lecture PDF."""
import requests
import sys

url = 'https://www.lassestorgaardjacobsen.dk/literature/al_lecture.pdf'

# Try with realistic browser headers
headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'application/pdf,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.9',
    'Referer': 'https://www.lassestorgaardjacobsen.dk/',
    'Connection': 'keep-alive'
}

try:
    response = requests.get(url, headers=headers, timeout=30, allow_redirects=True)
    print(f"Status: {response.status_code}")
    print(f"Content-Type: {response.headers.get('Content-Type', 'Unknown')}")
    print(f"Size: {len(response.content)} bytes")
    
    # Check if it's actually a PDF
    if response.content.startswith(b'%PDF'):
        print("✅ Valid PDF detected")
        with open('/books/lasse_lecture.pdf', 'wb') as f:
            f.write(response.content)
        print("✅ Saved PDF")
    elif b'<html' in response.content[:500].lower() or b'<!DOCTYPE' in response.content[:500]:
        print("⚠️  Received HTML instead of PDF (server blocking or error)")
        print(f"First 500 chars: {response.text[:500] if hasattr(response, 'text') else response.content[:500]}")
        # Try to extract text from HTML if it contains the content
        if 'ModSecurity' in response.text or 'Error' in response.text:
            print("❌ Server blocked request with ModSecurity")
    else:
        print("⚠️  Unknown content type")
        with open('/books/lasse_lecture.pdf', 'wb') as f:
            f.write(response.content)
        print("Saved anyway for inspection")
        
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()

