#!/usr/bin/env python3
"""Download training schedule template PDF."""
import requests

url = 'https://images.template.net/wp-content/uploads/2016/08/01091053/Athlete-Training-Schedule-Template.pdf'

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'application/pdf,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.9',
    'Referer': 'https://www.template.net/',
    'Connection': 'keep-alive'
}

try:
    response = requests.get(url, headers=headers, timeout=30, allow_redirects=True)
    print(f"Status: {response.status_code}")
    content_type = response.headers.get('Content-Type', 'Unknown')
    print(f"Content-Type: {content_type}")
    print(f"Size: {len(response.content)} bytes")
    
    # Check if it's actually a PDF
    if response.content.startswith(b'%PDF'):
        print("✅ Valid PDF detected")
        with open('/books/training_schedule_template.pdf', 'wb') as f:
            f.write(response.content)
        print("✅ Saved PDF")
    elif b'<html' in response.content[:500].lower() or b'<!DOCTYPE' in response.content[:500]:
        print("⚠️  Received HTML instead of PDF")
        print(f"First 500 chars: {response.text[:500] if hasattr(response, 'text') else response.content[:500]}")
    else:
        print("⚠️  Unknown content type, saving anyway")
        with open('/books/training_schedule_template.pdf', 'wb') as f:
            f.write(response.content)
        print("Saved for inspection")
        
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()

