#!/usr/bin/env python3
"""
Automated VitalSource Extraction

Extracts entire book from VitalSource web reader automatically.
Navigates through all pages and extracts text.
"""
import sys
import os
import time
import json
from pathlib import Path

try:
    from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False


def extract_vitalsource_book(
    book_url: str,
    output_file: str,
    email: str = None,
    password: str = None,
    max_pages: int = 1000
):
    """
    Automatically extract entire book from VitalSource.
    
    Args:
        book_url: VitalSource book URL
        output_file: Output text file path
        email: VitalSource login email
        password: VitalSource login password
        max_pages: Maximum pages to extract (safety limit)
    """
    if not PLAYWRIGHT_AVAILABLE:
        print("❌ Playwright not available.")
        print("   Install with: pip install playwright")
        print("   Then run: playwright install chromium")
        return False
    
    email = email or os.getenv("VITALSOURCE_EMAIL")
    password = password or os.getenv("VITALSOURCE_PASSWORD")
    
    if not email or not password:
        print("❌ Need VitalSource credentials:")
        print("   Set VITALSOURCE_EMAIL and VITALSOURCE_PASSWORD env vars")
        return False
    
    print("🚀 Starting automated VitalSource extraction...")
    print(f"📖 Book URL: {book_url}")
    print(f"💾 Output: {output_file}")
    
    all_text = []
    pages_extracted = 0
    
    with sync_playwright() as p:
        # Launch browser (headless mode for Docker)
        browser = p.chromium.launch(headless=True)  # Headless for Docker containers
        context = browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        )
        page = context.new_page()
        
        try:
            # Step 1: Login
            print("\n🔐 Logging into VitalSource...")
            page.goto("https://bookshelf.vitalsource.com/", wait_until="networkidle")
            time.sleep(2)
            
            # Check if login is needed
            try:
                email_input = page.locator('input[type="email"]').first
                if email_input.count() > 0 and email_input.is_visible(timeout=5000):
                    print("   Found login form, logging in...")
                    email_input.fill(email)
                    password_input = page.locator('input[type="password"]').first
                    password_input.fill(password)
                    
                    # Try different submit button selectors
                    submit_selectors = [
                        'button[type="submit"]',
                        'button:has-text("Sign in")',
                        'button:has-text("Log in")',
                        'input[type="submit"]',
                        '[type="submit"]'
                    ]
                    
                    submitted = False
                    for selector in submit_selectors:
                        try:
                            if page.locator(selector).count() > 0:
                                page.locator(selector).first.click(timeout=5000)
                                submitted = True
                                break
                        except:
                            continue
                    
                    if submitted:
                        page.wait_for_load_state("networkidle", timeout=10000)
                        time.sleep(3)
                        print("✅ Logged in")
                    else:
                        print("⚠️  Could not find submit button, trying to continue...")
                else:
                    print("✅ Already logged in or no login needed")
            except Exception as e:
                print(f"⚠️  Login check failed (may already be logged in): {e}")
                print("   Continuing...")
            
            # Step 2: Navigate to book
            print(f"\n📚 Opening book...")
            page.goto(book_url, wait_until="networkidle")
            time.sleep(5)  # Wait for reader to load
            
            # Step 3: Extract text from current page
            def extract_page_text():
                """Extract text from current page."""
                # Try multiple selectors
                selectors = [
                    'div[class*="reader"]',
                    'div[class*="content"]',
                    'div[class*="text"]',
                    'p',
                    '[role="textbox"]',
                    '.vs-reader-content',
                    '#reader-content'
                ]
                
                text_parts = []
                seen = set()
                
                for selector in selectors:
                    try:
                        elements = page.locator(selector).all()
                        for el in elements:
                            text = el.inner_text() if el.count() > 0 else ""
                            if text and len(text) > 30 and text not in seen:
                                seen.add(text)
                                text_parts.append(text)
                    except:
                        pass
                
                # Also get body text
                body_text = page.locator('body').inner_text()
                if body_text:
                    paragraphs = [p.strip() for p in body_text.split('\n\n') if len(p.strip()) > 30]
                    for para in paragraphs:
                        if para not in seen:
                            seen.add(para)
                            text_parts.append(para)
                
                return '\n\n'.join(text_parts)
            
            # Step 4: Navigate through pages and extract
            print("\n📄 Extracting pages...")
            print("   (This will take a while - be patient)")
            
            last_text = ""
            no_change_count = 0
            
            while pages_extracted < max_pages:
                # Extract current page
                page_text = extract_page_text()
                
                if page_text and len(page_text) > 100:
                    # Check if this is new content
                    if page_text != last_text:
                        all_text.append(page_text)
                        pages_extracted += 1
                        last_text = page_text
                        no_change_count = 0
                        
                        if pages_extracted % 10 == 0:
                            print(f"   ✅ Extracted {pages_extracted} pages... ({len(''.join(all_text))} chars)")
                    else:
                        no_change_count += 1
                        if no_change_count >= 3:
                            print(f"\n✅ Reached end of book (no new content for 3 pages)")
                            break
                else:
                    print(f"   ⚠️ Page {pages_extracted + 1} has little/no text, trying next...")
                    no_change_count += 1
                    if no_change_count >= 5:
                        print(f"\n✅ Reached end of book")
                        break
                
                # Try to navigate to next page
                # VitalSource uses various navigation methods
                next_clicked = False
                
                # Try different next button selectors
                next_selectors = [
                    'button[aria-label*="next"]',
                    'button[aria-label*="Next"]',
                    'button[title*="next"]',
                    'button[title*="Next"]',
                    '[class*="next"]',
                    '[data-testid*="next"]',
                    'button:has-text("Next")',
                    'button:has-text("→")',
                    'button:has-text(">")'
                ]
                
                for selector in next_selectors:
                    try:
                        if page.locator(selector).count() > 0:
                            page.locator(selector).first.click()
                            next_clicked = True
                            time.sleep(2)  # Wait for page to load
                            break
                    except:
                        pass
                
                # If no button found, try arrow key
                if not next_clicked:
                    try:
                        page.keyboard.press("ArrowRight")
                        time.sleep(2)
                        next_clicked = True
                    except:
                        pass
                
                # If still no navigation, try scrolling and clicking
                if not next_clicked:
                    try:
                        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                        time.sleep(1)
                        # Click on right side of page to advance
                        page.click('body', position={'x': 1800, 'y': 500})
                        time.sleep(2)
                    except:
                        pass
                
                # Small delay between pages
                time.sleep(1)
            
            # Step 5: Save extracted text
            if all_text:
                full_text = '\n\n--- PAGE BREAK ---\n\n'.join(all_text)
                
                # Ensure output directory exists
                output_dir = os.path.dirname(output_file)
                if output_dir:
                    os.makedirs(output_dir, exist_ok=True)
                
                with open(output_file, 'w', encoding='utf-8') as f:
                    f.write(full_text)
                
                print(f"\n✅ Extraction complete!")
                print(f"   📄 Pages extracted: {pages_extracted}")
                print(f"   📝 Total characters: {len(full_text)}")
                print(f"   💾 Saved to: {output_file}")
                return True
            else:
                print("\n❌ No text extracted")
                return False
                
        except Exception as e:
            print(f"\n❌ Error: {e}")
            import traceback
            traceback.print_exc()
            return False
        finally:
            browser.close()


def main():
    """Main function for command-line usage."""
    if len(sys.argv) < 3:
        print("Usage: python extract_vitalsource_automated.py <book_url> <output_file> [email] [password]")
        print("\nExample:")
        print("  python extract_vitalsource_automated.py 'https://bookshelf.vitalsource.com/...' daniels.txt")
        print("\nOr set env vars:")
        print("  export VITALSOURCE_EMAIL=your@email.com")
        print("  export VITALSOURCE_PASSWORD=yourpassword")
        sys.exit(1)
    
    book_url = sys.argv[1]
    output_file = sys.argv[2]
    email = sys.argv[3] if len(sys.argv) > 3 else None
    password = sys.argv[4] if len(sys.argv) > 4 else None
    
    print("⚠️  Note: This will open a browser window.")
    print("   You may need to manually navigate if automatic navigation fails.")
    print("   The script will extract text from each page automatically.\n")
    
    success = extract_vitalsource_book(book_url, output_file, email, password)
    
    if success:
        print("\n✅ Now run knowledge extraction:")
        print(f"   python scripts/extract_knowledge.py {output_file} 'Daniels Running Formula' 'Daniels' book")
    else:
        print("\n❌ Extraction failed")
        sys.exit(1)


if __name__ == "__main__":
    main()

