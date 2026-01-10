#!/usr/bin/env python3
"""
Download file from Google Drive
"""
import sys
import requests
import os

def download_google_drive_file(file_id: str, output_path: str):
    """Download file from Google Drive."""
    # Try direct download URL
    url = f"https://drive.google.com/uc?export=download&id={file_id}"
    
    print(f"Downloading from Google Drive...")
    print(f"File ID: {file_id}")
    print(f"URL: {url}")
    
    try:
        # First request might redirect for large files
        response = requests.get(url, allow_redirects=True, timeout=60, stream=True)
        
        print(f"Status: {response.status_code}")
        print(f"Content-Type: {response.headers.get('Content-Type', 'unknown')}")
        
        if response.status_code == 200:
            # Check if it's an HTML page (means file is too large or requires confirmation)
            content_type = response.headers.get('Content-Type', '')
            if 'text/html' in content_type:
                print("⚠️  Got HTML response - file may be too large or require confirmation")
                print("   Trying alternative method...")
                
                # Try with confirm parameter
                url_with_confirm = f"https://drive.google.com/uc?export=download&id={file_id}&confirm=t"
                response = requests.get(url_with_confirm, allow_redirects=True, timeout=60, stream=True)
                content_type = response.headers.get('Content-Type', '')
            
            # Check if we got actual file content
            if 'text/html' not in content_type:
                # Save file
                with open(output_path, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        f.write(chunk)
                
                file_size = os.path.getsize(output_path)
                print(f"✅ Downloaded {file_size} bytes to {output_path}")
                
                # Check file type
                with open(output_path, 'rb') as f:
                    header = f.read(10)
                    if header.startswith(b'%PDF'):
                        print("   File type: PDF")
                    elif header.startswith(b'PK'):
                        print("   File type: ZIP/EPUB/DOCX")
                    else:
                        print(f"   File type: Unknown (header: {header[:20]})")
                
                return True
            else:
                print("❌ Still got HTML - file may require authentication")
                print("   Content preview:")
                print(response.text[:500])
                return False
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
        print("Usage: python download_google_drive.py <file_id> <output_path>")
        print("\nExample:")
        print("  python download_google_drive.py 0B_zzkn1-wR0dVTVGN2VBNmZYaGc /books/file.pdf")
        sys.exit(1)
    
    file_id = sys.argv[1]
    output_path = sys.argv[2]
    
    success = download_google_drive_file(file_id, output_path)
    sys.exit(0 if success else 1)

