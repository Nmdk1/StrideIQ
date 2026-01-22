#!/usr/bin/env python3
"""
VitalSource Bookshelf Extraction Script

Extracts text from VitalSource web reader by scraping pages.
Requires browser automation (Selenium) to navigate through the book.
"""
import sys
import os
import time
from pathlib import Path

try:
    from selenium import webdriver
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.webdriver.chrome.options import Options
    SELENIUM_AVAILABLE = True
except ImportError:
    SELENIUM_AVAILABLE = False


def extract_from_vitalsource(url: str, output_file: str, email: str = None, password: str = None):
    """
    Extract text from VitalSource web reader.
    
    Args:
        url: VitalSource book URL
        output_file: Output text file path
        email: VitalSource login email (or use env var)
        password: VitalSource login password (or use env var)
    """
    if not SELENIUM_AVAILABLE:
        print("❌ Selenium not available. Install with: pip install selenium")
        print("   Also need ChromeDriver: https://chromedriver.chromium.org/")
        return False
    
    email = email or os.getenv("VITALSOURCE_EMAIL")
    password = password or os.getenv("VITALSOURCE_PASSWORD")
    
    if not email or not password:
        print("❌ Need VitalSource credentials:")
        print("   Set VITALSOURCE_EMAIL and VITALSOURCE_PASSWORD env vars")
        print("   Or pass as arguments")
        return False
    
    # Setup Chrome driver
    chrome_options = Options()
    chrome_options.add_argument("--headless")  # Run in background
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    
    try:
        driver = webdriver.Chrome(options=chrome_options)
    except Exception as e:
        print(f"❌ Could not start Chrome driver: {e}")
        print("   Install ChromeDriver: https://chromedriver.chromium.org/")
        return False
    
    text_content = []
    
    try:
        # Navigate to VitalSource
        print("Navigating to VitalSource...")
        driver.get("https://bookshelf.vitalsource.com/")
        
        # Login (if needed)
        try:
            email_input = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.ID, "email"))
            )
            email_input.send_keys(email)
            
            password_input = driver.find_element(By.ID, "password")
            password_input.send_keys(password)
            
            login_button = driver.find_element(By.CSS_SELECTOR, "button[type='submit']")
            login_button.click()
            
            print("Logged in...")
            time.sleep(3)
        except Exception as e:
            print(f"Note: Login may not be needed or page structure different: {e}")
        
        # Navigate to book URL
        print(f"Opening book: {url}")
        driver.get(url)
        time.sleep(5)  # Wait for page to load
        
        # Extract text from current page
        # VitalSource uses iframes and specific selectors
        try:
            # Try to find text content
            # VitalSource structure varies - may need to adjust selectors
            text_elements = driver.find_elements(By.CSS_SELECTOR, "p, div[class*='text'], span[class*='content']")
            
            for element in text_elements:
                text = element.text.strip()
                if text and len(text) > 10:  # Filter out short fragments
                    text_content.append(text)
            
            print(f"Extracted {len(text_content)} text blocks")
            
        except Exception as e:
            print(f"Warning: Could not extract text from page: {e}")
            print("VitalSource page structure may be different")
            print("Try manual extraction or check if EPUB download is available")
        
        # Note: To extract entire book, would need to:
        # 1. Navigate through all pages (click next button)
        # 2. Extract text from each page
        # 3. Handle pagination
        
        if text_content:
            # Write extracted text
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write('\n\n'.join(text_content))
            
            print(f"✅ Extracted {len(''.join(text_content))} characters to {output_file}")
            return True
        else:
            print("❌ No text extracted")
            return False
            
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        driver.quit()


def main():
    """Main function for command-line usage."""
    if len(sys.argv) < 3:
        print("Usage: python extract_from_vitalsource.py <vitalsource_url> <output_file> [email] [password]")
        print("\nExample:")
        print("  python extract_from_vitalsource.py 'https://bookshelf.vitalsource.com/...' output.txt")
        print("\nOr set env vars:")
        print("  export VITALSOURCE_EMAIL=your_email_here")
        print("  export VITALSOURCE_PASSWORD=yourpassword")
        sys.exit(1)
    
    url = sys.argv[1]
    output_file = sys.argv[2]
    email = sys.argv[3] if len(sys.argv) > 3 else None
    password = sys.argv[4] if len(sys.argv) > 4 else None
    
    success = extract_from_vitalsource(url, output_file, email, password)
    
    if success:
        print("✅ Extraction complete!")
        print(f"✅ Now run: python scripts/extract_knowledge.py {output_file} 'Daniels Running Formula' 'Daniels' book")
    else:
        print("❌ Extraction failed")
        sys.exit(1)


if __name__ == "__main__":
    main()

