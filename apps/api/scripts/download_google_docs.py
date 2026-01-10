#!/usr/bin/env python3
"""
Download Google Docs document
"""
import sys
import requests
import re

def extract_doc_id(url: str) -> str:
    """Extract document ID from Google Docs URL."""
    # Pattern: /d/{DOC_ID}/
    match = re.search(r'/d/([a-zA-Z0-9_-]+)', url)
    if match:
        return match.group(1)
    return ""

def download_google_doc(doc_id: str, output_path: str, format: str = "txt"):
    """Download Google Docs document."""
    if format == "txt":
        url = f"https://docs.google.com/document/d/{doc_id}/export?format=txt"
    elif format == "pdf":
        url = f"https://docs.google.com/document/d/{doc_id}/export?format=pdf"
    else:
        print(f"❌ Unknown format: {format}")
        return False
    
    print(f"Downloading Google Doc...")
    print(f"Doc ID: {doc_id}")
    print(f"Format: {format}")
    print(f"URL: {url}")
    
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        response = requests.get(url, headers=headers, timeout=60, stream=True, allow_redirects=True)
        
        print(f"Status: {response.status_code}")
        print(f"Content-Type: {response.headers.get('Content-Type', 'unknown')}")
        
        if response.status_code == 200:
            # Check if we got actual content (not HTML error page)
            content_type = response.headers.get('Content-Type', '')
            if 'text/html' in content_type:
                print("⚠️  Got HTML response - document may require authentication")
                print("   Trying PDF format...")
                return download_google_doc(doc_id, output_path.replace('.txt', '.pdf'), "pdf")
            
            # Save file
            file_size = 0
            with open(output_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        file_size += len(chunk)
            
            print(f"✅ Downloaded {file_size} bytes to {output_path}")
            return True
        else:
            print(f"❌ Download failed with status {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python download_google_docs.py <doc_url> <output_path>")
        print("\nExample:")
        print("  python download_google_docs.py 'https://docs.google.com/document/d/...' /books/marathon_plan.txt")
        sys.exit(1)
    
    doc_url = sys.argv[1]
    output_path = sys.argv[2]
    
    doc_id = extract_doc_id(doc_url)
    if not doc_id:
        print(f"❌ Could not extract document ID from URL: {doc_url}")
        sys.exit(1)
    
    # Determine format from output path
    format = "pdf" if output_path.endswith(".pdf") else "txt"
    
    success = download_google_doc(doc_id, output_path, format)
    sys.exit(0 if success else 1)

