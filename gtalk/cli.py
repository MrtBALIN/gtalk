#!/usr/bin/env python3

import sys
import time
import platform
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup
import urllib.parse
import re


class GoogleAIMode:
    def __init__(self):
        self.driver = None
        self.memory = ""
        self.is_windows = platform.system() == "Windows"
        self.retry_delay = 3 if self.is_windows else 2

    def init_driver(self):
        """Initialize browser with cross-platform optimizations"""
        if self.driver is not None:
            return

        print("🔄 Initializing browser...")
        options = Options()
        
        # Platform-specific configurations
        if self.is_windows:
            options.add_argument('--headless=new')  # Better for Windows
        else:
            options.add_argument('--headless')
        
        # Core options
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--disable-blink-features=AutomationControlled')
        options.add_argument('--disable-infobars')
        options.add_argument('--disable-extensions')
        options.add_argument('--disable-gpu')  # Helps with headless stability
        options.add_argument('--lang=en-US')
        options.add_argument('--window-size=1920,1080')
        
        # User agent (Windows-based for consistency)
        user_agent = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        options.add_argument(f'--user-agent={user_agent}')
        
        # Anti-detection
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option('useAutomationExtension', False)
        options.add_experimental_option("prefs", {
            "profile.default_content_setting_values.notifications": 2,
            "profile.default_content_setting_values.geolocation": 2
        })

        try:
            service = Service()
            self.driver = webdriver.Chrome(service=service, options=options)
            
            # Enhanced stealth scripts
            self.driver.execute_cdp_cmd('Network.setUserAgentOverride', {
                "userAgent": user_agent
            })
            self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            self.driver.execute_script("Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]})")
            self.driver.execute_script("Object.defineProperty(navigator, 'languages', {get: () => ['en-US', 'en']})")
            
            # Warm-up session to avoid first-request CAPTCHA
            print("🔄 Warming up session...")
            self.driver.get("https://www.google.com")
            time.sleep(self.retry_delay)
            
            print("✓ Browser ready!\n")
            
        except Exception as e:
            print(f"❌ Failed to initialize browser: {str(e)}")
            print("Make sure Chrome and ChromeDriver are installed and in PATH")
            sys.exit(1)

    def extract_summary_from_html(self, html):
        """Extract AI summary from Google's response"""
        soup = BeautifulSoup(html, 'html.parser')
        main_container = soup.select_one('div.mZJni.Dn7Fzd')
        if not main_container:
            return None

        result = []

        for text_div in main_container.select('div.Y3BBE'):
            if text_div.find_parent('div', class_='r1PmQe'):
                continue
            text = text_div.get_text(separator=' ', strip=True)
            text = re.sub(r'\s+', ' ', text).strip()
            if text:
                result.append(('text', text))

        for code_container in main_container.select('div.r1PmQe'):
            lang_div = code_container.select_one('div.vVRw1d')
            language = lang_div.get_text(strip=True) if lang_div else ''
            code_elem = code_container.select_one('pre code')
            if code_elem:
                code = code_elem.get_text()
                result.append(('code', language, code))
            next_text = code_container.find_next_sibling('div', class_='Y3BBE')
            if next_text:
                label = next_text.get_text(strip=True)
                if label and len(label) < 50:
                    result.append(('text', label))

        return result if result else None

    def extract_first_paragraph_100_words(self, content_blocks):
        """Extract first paragraph and cut to 100 words for memory"""
        for item in content_blocks:
            if item[0] == 'text':
                words = item[1].split()
                return " ".join(words[:100])
        return ""

    def query(self, raw_query, retry_count=0, max_retries=2):
        """Execute query with automatic retry on CAPTCHA"""
        try:
            if self.driver is None:
                self.init_driver()

            # Memory context
            memory_part = f"Previous summary: {self.memory}. " if self.memory else ""

            # Instruction to get concise summary first
            trick = (
                "Return a summary of your answer in no more than 100 words in the first paragraph, "
                "then provide the full original answer normally."
            )

            final_query_text = f"{memory_part}{trick} Users query: {raw_query}"
            encoded = urllib.parse.quote_plus(final_query_text)
            
            # URL with English language parameters
            url = f"https://www.google.com/search?udm=50&aep=11&hl=en&lr=lang_en&q={encoded}"

            print("🔍 Searching...")
            self.driver.get(url)

            # Platform-specific wait times
            initial_wait = 4 if self.is_windows else 3
            time.sleep(initial_wait)
            
            # Check for CAPTCHA
            page_source_lower = self.driver.page_source.lower()
            if "captcha" in page_source_lower or "unusual traffic" in page_source_lower:
                if retry_count < max_retries:
                    wait_time = (retry_count + 1) * self.retry_delay
                    print(f"⚠️  CAPTCHA detected. Retrying in {wait_time}s... (Attempt {retry_count + 2}/{max_retries + 1})")
                    time.sleep(wait_time)
                    return self.query(raw_query, retry_count + 1, max_retries)
                else:
                    print("❌ CAPTCHA detected. Max retries reached.")
                    print("💡 Tip: Wait a few minutes before trying again.\n")
                    return

            # Wait for content to load
            try:
                WebDriverWait(self.driver, 10).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "div.Y3BBE, div.kCrYT, div.hgKElc"))
                )
            except:
                pass

            time.sleep(2)
            html = self.driver.page_source

            content = self.extract_summary_from_html(html)

            if not content:
                print("❌ No AI summary found.")
                print("💡 Google AI Mode might not have generated a response for this query.\n")
                return

            # Update memory with new summary
            new_summary = self.extract_first_paragraph_100_words(content)
            if new_summary:
                self.memory = new_summary

            # Display results
            print("\n" + "="*60)
            for item in content:
                if item[0] == 'text':
                    print(item[1])
                    print()
                elif item[0] == 'code':
                    language = item[1]
                    code = item[2]
                    if language:
                        print(f"```{language}")
                    else:
                        print("```")
                    print(code.rstrip())
                    print("```")
                    print()
            print("="*60 + "\n")

        except KeyboardInterrupt:
            raise
        except Exception as e:
            print(f"❌ Error: {str(e)}")
            if "chrome not reachable" in str(e).lower():
                print("💡 Browser crashed. Reinitializing...")
                self.driver = None
                if retry_count < max_retries:
                    return self.query(raw_query, retry_count + 1, max_retries)
            print()

    def close(self):
        """Clean up browser resources"""
        if self.driver:
            try:
                self.driver.quit()
            except:
                pass
            self.driver = None


def clear_screen():
    """Clear terminal screen (cross-platform)"""
    import os
    os.system('cls' if platform.system() == "Windows" else 'clear')


def print_help():
    """Display help information"""
    print("\n" + "="*60)
    print("Commands:")
    print("  [text]    - Query Google AI Mode")
    print("  help      - Show this help message")
    print("  clear     - Clear terminal screen")
    print("  reset     - Reset conversation memory")
    print("  quit      - Exit the program")
    print("="*60 + "\n")


def main():
    """Main interactive loop"""
    clear_screen()
    print("="*60)
    print("  Google AI Mode - Interactive Terminal Query Tool")
    print("="*60)
    print(f"  Platform: {platform.system()} | Python: {platform.python_version()}")
    print("="*60)
    print("\nType 'help' for commands, 'quit' to exit\n")

    ai = GoogleAIMode()
    
    # Pre-initialize browser to avoid first-query issues
    ai.init_driver()

    try:
        while True:
            try:
                q = input("Query> ").strip()
            except EOFError:
                print("\nExiting...")
                break

            if not q:
                continue

            q_lower = q.lower()
            
            if q_lower in ['quit', 'exit', 'q']:
                print("Goodbye!")
                break
            elif q_lower == 'help':
                print_help()
                continue
            elif q_lower == 'clear':
                clear_screen()
                continue
            elif q_lower == 'reset':
                ai.memory = ""
                print("✓ Conversation memory reset.\n")
                continue

            print()
            ai.query(q)

    except KeyboardInterrupt:
        print("\n\n👋 Interrupted. Goodbye!")

    finally:
        ai.close()


if __name__ == "__main__":
    if len(sys.argv) > 1:
        # Command-line mode
        ai = GoogleAIMode()
        try:
            query_text = " ".join(sys.argv[1:])
            print(f"Querying: {query_text}\n")
            ai.query(query_text)
        finally:
            ai.close()
    else:
        # Interactive mode
        main()
