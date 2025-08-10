import asyncio
import aiohttp
import logging
import os
import time
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright, Page, Browser
from typing import Optional, Dict, Any
import re

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class WebScraper:
    def __init__(self):
        self.browser: Optional[Browser] = None
        self.playwright = None
        self.session: Optional[aiohttp.ClientSession] = None
        
        # Site-specific limits for problematic domains
        self.PROBLEMATIC_SITES = {
            'vcsheet.com': {
                'max_scrolls': 3,
                'max_items': 5000,
                'max_time': 30,
                'max_height': 100000,
                'max_pages': 2
            },
            'crunchbase.com': {
                'max_scrolls': 5,
                'max_items': 10000,
                'max_time': 45,
                'max_height': 200000,
                'max_pages': 3
            },
            'linkedin.com': {
                'max_scrolls': 4,
                'max_items': 3000,
                'max_time': 40,
                'max_height': 150000,
                'max_pages': 2
            },
            'indeed.com': {
                'max_scrolls': 6,
                'max_items': 8000,
                'max_time': 50,
                'max_height': 300000,
                'max_pages': 4
            },
            'glassdoor.com': {
                'max_scrolls': 4,
                'max_items': 4000,
                'max_time': 35,
                'max_height': 180000,
                'max_pages': 2
            }
        }
        
    async def _ensure_browser(self):
        """Ensure Playwright browser is initialized"""
        if not self.browser or not self.browser.is_connected():
            # Clean up any existing browser first
            if self.browser:
                try:
                    await self.browser.close()
                except:
                    pass
            if self.playwright:
                try:
                    await self.playwright.stop()
                except:
                    pass
            
            self.playwright = await async_playwright().start()
            self.browser = await self.playwright.chromium.launch(
                headless=True,
                args=[
                    '--no-sandbox', 
                    '--disable-dev-shm-usage',
                    '--disable-blink-features=AutomationControlled',
                    '--disable-features=VizDisplayCompositor',
                    '--memory-pressure-off'
                ]
            )
            
    async def _ensure_session(self):
        """Ensure aiohttp session is initialized"""
        if not self.session:
            timeout = aiohttp.ClientTimeout(total=30)
            self.session = aiohttp.ClientSession(
                timeout=timeout,
                headers={
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
                }
            )
    
    async def scrape_url(self, url: str) -> Dict[str, Any]:
        """
        Main scraping method that tries multiple approaches
        """
        logger.info(f"Starting scrape for URL: {url}")
        
        try:
            # First try with simple HTTP request + BeautifulSoup
            content = await self._scrape_with_requests(url)
            if self._is_content_sufficient(content.get('html', '')):
                logger.info("Successfully scraped with HTTP requests")
                return content
                
        except Exception as e:
            logger.warning(f"HTTP scraping failed: {e}")
        
        try:
            # Fallback to Playwright for dynamic content
            content = await self._scrape_with_playwright(url)
            logger.info("Successfully scraped with Playwright")
            return content
            
        except Exception as e:
            logger.error(f"Playwright scraping failed: {e}")
            raise Exception(f"Failed to scrape URL {url}: {str(e)}")
    
    async def _scrape_with_requests(self, url: str) -> Dict[str, Any]:
        """Scrape using aiohttp + BeautifulSoup"""
        await self._ensure_session()
        
        async with self.session.get(url) as response:
            if response.status != 200:
                raise Exception(f"HTTP {response.status}: {response.reason}")
                
            html = await response.text()
            soup = BeautifulSoup(html, 'html.parser')
            
            # Extract metadata
            title = soup.title.string if soup.title else ""
            meta_desc = ""
            if soup.find('meta', attrs={'name': 'description'}):
                meta_desc = soup.find('meta', attrs={'name': 'description'}).get('content', '')
            
            # Extract social media and contact info before cleaning
            social_links = self._extract_social_links(soup)
            emails = self._extract_emails(html, soup)
            
            # Clean HTML - remove script, style, and other non-content tags
            for tag in soup(['script', 'style', 'nav', 'header', 'footer', 'aside']):
                tag.decompose()
            
            # Extract clean text
            text_content = soup.get_text()
            clean_text = self._clean_text(text_content)
            
            return {
                'url': url,
                'title': title.strip() if title else '',
                'meta_description': meta_desc.strip(),
                'html': str(soup),
                'text': clean_text,
                'social_links': social_links,
                'emails': emails,
                'method': 'requests'
            }
    
    async def _scrape_with_playwright(self, url: str) -> Dict[str, Any]:
        """Scrape using Playwright for dynamic content with infinite scroll and pagination"""
        page = None
        max_retries = 3
        
        for attempt in range(max_retries):
            try:
                # Ensure fresh browser for each attempt
                await self._ensure_browser()
                
                # Create new page with extended settings
                page = await self.browser.new_page()
                
                # Set longer timeouts for complex pages
                page.set_default_timeout(60000)  # 60 seconds
                page.set_default_navigation_timeout(60000)
                
                # Navigate to page with retry logic
                try:
                    await page.goto(url, wait_until='domcontentloaded', timeout=45000)
                    logger.info(f"Successfully navigated to {url}")
                except Exception as nav_error:
                    logger.warning(f"Navigation attempt {attempt + 1} failed: {nav_error}")
                    if attempt == max_retries - 1:
                        raise nav_error
                    await page.close()
                    continue
                
                # Wait for initial content to load
                await page.wait_for_timeout(3000)
                
                # Handle infinite scroll and pagination with error recovery
                await self._handle_dynamic_content(page)
                
                break  # Success, exit retry loop
                
            except Exception as e:
                logger.error(f"Playwright scraping attempt {attempt + 1} failed: {e}")
                if page:
                    try:
                        await page.close()
                    except:
                        pass
                    page = None
                
                if attempt == max_retries - 1:
                    # Last attempt failed
                    if "Target page, context or browser has been closed" in str(e):
                        logger.error("Browser was closed unexpectedly - reinitializing")
                        await self.cleanup()
                        await self._ensure_browser()
                    raise e
                
                # Wait before retry
                await asyncio.sleep(2)
        
        if not page:
            raise Exception("Failed to create page after all retries")
        
        try:
            # Extract page content
            title = await page.title()
            html = await page.content()
            
            # Get clean text content
            text_content = await page.evaluate('''() => {
                // Remove script, style, and other non-content elements
                const elementsToRemove = document.querySelectorAll('script, style, nav, header, footer, aside');
                elementsToRemove.forEach(el => el.remove());
                
                // Get clean text
                return document.body.innerText || document.body.textContent || '';
            }''')
            
            # Try to get meta description
            meta_desc = await page.evaluate('''() => {
                const metaDesc = document.querySelector('meta[name="description"]');
                return metaDesc ? metaDesc.content : '';
            }''')
            
            # Parse with BeautifulSoup to extract social links and emails
            soup = BeautifulSoup(html, 'html.parser')
            social_links = self._extract_social_links(soup)
            emails = self._extract_emails(html, soup)
            
            clean_text = self._clean_text(text_content)
            
            return {
                'url': url,
                'title': title.strip(),
                'meta_description': meta_desc.strip(),
                'html': html,
                'text': clean_text,
                'social_links': social_links,
                'emails': emails,
                'method': 'playwright'
            }
            
        finally:
            await page.close()
    
    def _clean_text(self, text: str) -> str:
        """Clean and normalize extracted text"""
        if not text:
            return ""
            
        # Replace multiple whitespaces with single space
        text = re.sub(r'\s+', ' ', text)
        
        # Remove excessive newlines
        text = re.sub(r'\n\s*\n', '\n\n', text)
        
        # Strip leading/trailing whitespace
        text = text.strip()
        
        return text
    
    def _is_content_sufficient(self, html: str) -> bool:
        """Check if scraped content has sufficient information"""
        if not html:
            return False
            
        soup = BeautifulSoup(html, 'html.parser')
        text = soup.get_text()
        
        # Consider content sufficient if it has reasonable amount of text
        # and doesn't look like a blocked/error page
        word_count = len(text.split())
        
        if word_count < 50:
            return False
            
        # Check for common blocking indicators
        blocking_indicators = [
            'access denied',
            'blocked',
            'cloudflare',
            'please enable javascript',
            'bot detection'
        ]
        
        text_lower = text.lower()
        for indicator in blocking_indicators:
            if indicator in text_lower:
                return False
                
        return True
    
    def _get_site_specific_limits(self, url: str) -> Dict[str, int]:
        """Get site-specific limits based on URL domain"""
        try:
            from urllib.parse import urlparse
            domain = urlparse(url).netloc.lower()
            
            # Remove www. prefix for matching
            if domain.startswith('www.'):
                domain = domain[4:]
            
            # Check if domain matches any problematic site
            for site_key, limits in self.PROBLEMATIC_SITES.items():
                if site_key in domain:
                    logger.info(f"Applying site-specific limits for {domain}: {limits}")
                    return limits
            
            # Return empty dict for default limits
            return {}
            
        except Exception as e:
            logger.warning(f"Error getting site-specific limits: {e}")
            return {}
    
    async def cleanup(self):
        """Clean up resources"""
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()
        if self.session:
            await self.session.close()
            
    async def __aenter__(self):
        return self
        
    def _extract_social_links(self, soup: BeautifulSoup) -> Dict[str, list]:
        """Extract social media links from the page"""
        social_patterns = {
            'facebook': ['facebook.com', 'fb.com'],
            'twitter': ['twitter.com', 'x.com'],
            'linkedin': ['linkedin.com'],
            'instagram': ['instagram.com'],
            'youtube': ['youtube.com', 'youtu.be'],
            'github': ['github.com'],
            'tiktok': ['tiktok.com'],
            'discord': ['discord.gg', 'discord.com'],
            'telegram': ['t.me', 'telegram.me'],
            'whatsapp': ['wa.me', 'whatsapp.com']
        }
        
        social_links = {}
        
        # Find all links
        for link in soup.find_all('a', href=True):
            href = link.get('href', '').lower()
            
            for platform, patterns in social_patterns.items():
                if any(pattern in href for pattern in patterns):
                    if platform not in social_links:
                        social_links[platform] = []
                    
                    # Clean and store the link
                    clean_link = link.get('href')
                    if clean_link not in social_links[platform]:
                        social_links[platform].append({
                            'url': clean_link,
                            'text': link.get_text().strip(),
                            'title': link.get('title', '').strip()
                        })
        
        return social_links
    
    def _extract_emails(self, html: str, soup: BeautifulSoup) -> list:
        """Extract email addresses from the page with comprehensive patterns"""
        import re
        
        emails = set()
        
        # Multiple email patterns for different formats
        email_patterns = [
            # Standard email pattern
            r'\b[A-Za-z0-9](?:[A-Za-z0-9._-]*[A-Za-z0-9])?@[A-Za-z0-9](?:[A-Za-z0-9.-]*[A-Za-z0-9])?\.[A-Za-z]{2,}\b',
            # More permissive pattern
            r'[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}',
            # Pattern for emails with spaces (sometimes used to avoid spam)
            r'[A-Za-z0-9._%+-]+\s*@\s*[A-Za-z0-9.-]+\s*\.\s*[A-Za-z]{2,}',
        ]
        
        # Get text content for searching
        text_content = soup.get_text()
        full_html = html.lower()
        
        # Method 1: Find emails using multiple patterns
        for pattern in email_patterns:
            found_emails = re.findall(pattern, text_content, re.IGNORECASE)
            emails.update(found_emails)
            
            html_emails = re.findall(pattern, html, re.IGNORECASE)
            emails.update(html_emails)
        
        # Method 2: Find emails in mailto links
        for link in soup.find_all('a', href=True):
            href = link.get('href', '').lower()
            if href.startswith('mailto:'):
                email = href.replace('mailto:', '').split('?')[0].split('#')[0]  # Remove query params and fragments
                if email:
                    emails.add(email)
        
        # Method 3: Look for obfuscated emails (at, dot notation)
        obfuscated_patterns = [
            # "name at domain dot com" format
            r'([A-Za-z0-9._%+-]+)\s*(?:at|AT|@)\s*([A-Za-z0-9.-]+)\s*(?:dot|DOT|\.)\s*([A-Za-z]{2,})',
            # "name[at]domain[dot]com" format
            r'([A-Za-z0-9._%+-]+)\s*\[at\]\s*([A-Za-z0-9.-]+)\s*\[dot\]\s*([A-Za-z]{2,})',
            # "name (at) domain (dot) com" format
            r'([A-Za-z0-9._%+-]+)\s*\(at\)\s*([A-Za-z0-9.-]+)\s*\(dot\)\s*([A-Za-z]{2,})',
        ]
        
        for pattern in obfuscated_patterns:
            matches = re.findall(pattern, text_content, re.IGNORECASE)
            for match in matches:
                if len(match) == 3:
                    email = f"{match[0]}@{match[1]}.{match[2]}".replace(' ', '')
                    emails.add(email.lower())
        
        # Method 4: Look in specific HTML attributes that might contain emails
        for element in soup.find_all(['a', 'span', 'div', 'p', 'td'], string=True):
            for attr in ['data-email', 'data-mail', 'title', 'alt']:
                attr_value = element.get(attr, '')
                if '@' in attr_value and '.' in attr_value:
                    potential_emails = re.findall(email_patterns[1], attr_value, re.IGNORECASE)
                    emails.update(potential_emails)
        
        # Method 5: Look for JavaScript-obfuscated emails
        js_patterns = [
            # JavaScript string concatenation like: 'user' + '@' + 'domain.com'
            r"['\"]([A-Za-z0-9._%+-]+)['\"\s]*\+\s*['\"]@['\"\s]*\+\s*['\"]([A-Za-z0-9.-]+\.[A-Za-z]{2,})['\"]",
            # document.write patterns
            r"document\.write\(['\"]([^'\"]*@[^'\"]*\.[A-Za-z]{2,})['\"]",
        ]
        
        for pattern in js_patterns:
            matches = re.findall(pattern, html, re.IGNORECASE)
            for match in matches:
                if isinstance(match, tuple) and len(match) == 2:
                    email = f"{match[0]}@{match[1]}"
                    emails.add(email.lower())
                elif isinstance(match, str):
                    emails.add(match.lower())
        
        # Method 6: Look in JSON-LD structured data
        json_ld_scripts = soup.find_all('script', type='application/ld+json')
        for script in json_ld_scripts:
            try:
                import json
                data = json.loads(script.string or '')
                self._extract_emails_from_json(data, emails)
            except:
                continue
        
        # Clean and validate emails
        cleaned_emails = []
        skip_domains = ['example.com', 'domain.com', 'email.com', 'test.com', 'sampleemail.com', 'youremail.com']
        
        for email in emails:
            # Clean up the email
            email = email.strip().lower().replace(' ', '')
            
            # Additional filtering for common false positives
            skip_patterns = [
                'inform@ion',  # Common false positive from "information"
                'contact@us',  # From "contact us"  
                'more@info',   # From "more information"
                '@you',        # From various text
                '@us',         # From various text
                '@it',         # From various text
            ]
            
            # Basic validation
            if (len(email) > 5 and 
                '@' in email and 
                '.' in email.split('@')[-1] and
                not any(skip in email for skip in skip_domains) and
                not any(pattern in email for pattern in skip_patterns) and
                not email.endswith('.png') and
                not email.endswith('.jpg') and
                not email.endswith('.gif') and
                len(email.split('@')[0]) >= 2 and  # Username should be at least 2 chars
                len(email.split('@')[1].split('.')[0]) >= 2):  # Domain should be at least 2 chars
                
                # Final regex validation
                if re.match(r'^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$', email):
                    cleaned_emails.append(email)
        
        final_emails = list(set(cleaned_emails))  # Remove duplicates
        logger.info(f"Email extraction found {len(final_emails)} emails: {final_emails}")
        return final_emails
    
    def _extract_emails_from_json(self, data, emails_set):
        """Recursively extract emails from JSON-LD structured data"""
        if isinstance(data, dict):
            for key, value in data.items():
                if key.lower() in ['email', 'emailaddress', 'contactpoint'] and isinstance(value, str):
                    if '@' in value:
                        emails_set.add(value.lower())
                elif isinstance(value, (dict, list)):
                    self._extract_emails_from_json(value, emails_set)
        elif isinstance(data, list):
            for item in data:
                self._extract_emails_from_json(item, emails_set)
    
    async def _handle_dynamic_content(self, page: Page):
        """Handle infinite scroll, pagination, and dynamic content loading with comprehensive limits"""
        logger.info("Handling dynamic content loading...")
        
        try:
            # Check if page is still accessible
            if page.is_closed():
                logger.warning("Page was closed before dynamic content handling")
                return
            
            # Track initial content and timing
            initial_height = await page.evaluate('document.body.scrollHeight')
            initial_items_count = await self._count_content_items(page)
            start_time = time.time()
            
            # Get site-specific limits or use defaults
            site_limits = self._get_site_specific_limits(page.url)
            max_scrolls = site_limits.get('max_scrolls', int(os.getenv('MAX_SCROLL_ATTEMPTS', 20)))
            max_pages = site_limits.get('max_pages', int(os.getenv('MAX_PAGINATION_PAGES', 5)))
            max_time_seconds = site_limits.get('max_time', int(os.getenv('MAX_DYNAMIC_TIME', 60)))
            max_height = site_limits.get('max_height', int(os.getenv('MAX_PAGE_HEIGHT', 500000)))
            max_items = site_limits.get('max_items', int(os.getenv('MAX_CONTENT_ITEMS', 50000)))
            
            logger.info(f"Using limits for site: scrolls={max_scrolls}, items={max_items}, time={max_time_seconds}s")
            
            scroll_attempts = 0
            page_attempts = 0
            no_change_count = 0
            last_significant_change = start_time
            consecutive_large_changes = 0
            max_consecutive_changes = 5  # Stop after 5 consecutive large changes
            
            while (scroll_attempts < max_scrolls and 
                   no_change_count < 3 and
                   time.time() - start_time < max_time_seconds):
                try:
                    # Check if page is still accessible
                    if page.is_closed():
                        logger.warning("Page closed during dynamic content loading")
                        break
                    
                    scroll_attempts += 1
                    current_time = time.time()
                    
                    # Method 1: Try infinite scroll
                    await self._perform_infinite_scroll(page)
                    
                    # Method 2: Look for pagination buttons (less frequently)
                    if scroll_attempts % 8 == 0 and page_attempts < max_pages:  # Every 8 scrolls instead of 5
                        pagination_success = await self._handle_pagination(page)
                        if pagination_success:
                            page_attempts += 1
                            await page.wait_for_timeout(2000)  # Reduced wait time
                    
                    # Method 3: Look for "Load More" buttons (less frequently)
                    if scroll_attempts % 4 == 0:  # Only every 4th scroll
                        await self._click_load_more_buttons(page)
                    
                    # Check if content has changed
                    try:
                        new_height = await page.evaluate('document.body.scrollHeight')
                        new_items_count = await self._count_content_items(page)
                    except Exception as eval_error:
                        logger.warning(f"Failed to evaluate page content: {eval_error}")
                        break
                    
                    # Check comprehensive limits
                    if new_height > max_height:
                        logger.warning(f"Page height limit reached: {new_height} > {max_height}px")
                        break
                    
                    if new_items_count > max_items:
                        logger.warning(f"Content items limit reached: {new_items_count} > {max_items} items")
                        break
                    
                    # Detect significant changes (not just any change)
                    height_change = new_height - initial_height
                    items_change = new_items_count - initial_items_count
                    
                    # CRITICAL FIX: Much stricter thresholds to prevent infinite loops
                    significant_change = (height_change > 5000) or (items_change > 1000)
                    
                    # CRITICAL FIX: Detect excessive growth patterns
                    if items_change > 5000:
                        logger.warning(f"Excessive content growth detected: +{items_change} items in one iteration")
                        logger.warning("Stopping to prevent infinite expansion")
                        break
                    
                    # CRITICAL FIX: Track consecutive large changes
                    if items_change > 2000:  # Large change threshold
                        consecutive_large_changes += 1
                        if consecutive_large_changes >= max_consecutive_changes:
                            logger.warning(f"Too many consecutive large changes ({consecutive_large_changes}), stopping")
                            break
                    else:
                        consecutive_large_changes = 0  # Reset counter
                    
                    if significant_change:
                        logger.info(f"Content expanded - Height: {initial_height}→{new_height} (+{height_change}), Items: {initial_items_count}→{new_items_count} (+{items_change})")
                        initial_height = new_height
                        initial_items_count = new_items_count
                        no_change_count = 0
                        last_significant_change = current_time
                        
                        # Shorter wait for new content
                        await page.wait_for_timeout(1500)  # Reduced from 2000
                    else:
                        no_change_count += 1
                        await page.wait_for_timeout(800)   # Reduced from 1000
                        
                        # Additional check: if no significant change for too long, stop
                        if current_time - last_significant_change > 20:  # 20 seconds
                            logger.info("No significant content changes for 20 seconds, stopping dynamic loading")
                            break
                        
                except Exception as e:
                    logger.warning(f"Error during dynamic content loading (attempt {scroll_attempts}): {e}")
                    if "Target page, context or browser has been closed" in str(e):
                        logger.error("Page closed during dynamic content handling")
                        break
                    # Continue with next attempt
                    no_change_count += 1
            
            # Final summary with time and limits info
            try:
                final_items_count = await self._count_content_items(page) if not page.is_closed() else initial_items_count
                final_height = await page.evaluate('document.body.scrollHeight') if not page.is_closed() else initial_height
                total_time = time.time() - start_time
                
                # Determine why we stopped
                stop_reason = "completed"
                if scroll_attempts >= max_scrolls:
                    stop_reason = "max_scrolls_reached"
                elif total_time >= max_time_seconds:
                    stop_reason = "time_limit_reached"
                elif final_height >= max_height:
                    stop_reason = "height_limit_reached"
                elif final_items_count >= max_items:
                    stop_reason = "items_limit_reached"
                elif no_change_count >= 3:
                    stop_reason = "no_changes_detected"
                
                logger.info(f"Dynamic content loading {stop_reason} - Final: {final_items_count} items, {final_height}px height, {scroll_attempts} scrolls, {page_attempts} pages, {total_time:.1f}s")
            except Exception as e:
                logger.warning(f"Could not get final statistics: {e}")
                
        except Exception as e:
            logger.error(f"Dynamic content handling failed: {e}")
            # Continue with whatever content we have
    
    async def _perform_infinite_scroll(self, page: Page):
        """Perform smooth infinite scroll to trigger lazy loading"""
        try:
            # Scroll to bottom
            await page.evaluate('''() => {
                window.scrollTo(0, document.body.scrollHeight);
            }''')
            
            # Wait for potential lazy loading
            await page.wait_for_timeout(1500)
            
            # Scroll up a bit and down again to trigger more loading
            await page.evaluate('''() => {
                window.scrollBy(0, -200);
                setTimeout(() => window.scrollTo(0, document.body.scrollHeight), 500);
            }''')
            
            await page.wait_for_timeout(1000)
            
        except Exception as e:
            logger.warning(f"Infinite scroll failed: {e}")
    
    async def _handle_pagination(self, page: Page) -> bool:
        """Look for and click pagination buttons"""
        try:
            # Common pagination selectors
            pagination_selectors = [
                'button[aria-label*="Next"]',
                'button:has-text("Next")',
                'a:has-text("Next")',
                'button:has-text("Load more")',
                'button:has-text("Show more")',
                '.pagination button:last-child',
                '[data-testid*="next"]',
                '[class*="next"]',
                '[class*="pagination"] button:not([disabled]):last-child',
                'button[class*="load"]',
                'a[rel="next"]'
            ]
            
            for selector in pagination_selectors:
                try:
                    # Check if the element exists and is visible
                    element = await page.query_selector(selector)
                    if element:
                        is_visible = await element.is_visible()
                        is_enabled = await element.is_enabled()
                        
                        if is_visible and is_enabled:
                            logger.info(f"Found pagination element: {selector}")
                            await element.click()
                            await page.wait_for_timeout(2000)  # Wait for navigation/loading
                            return True
                            
                except Exception as e:
                    continue  # Try next selector
            
            return False
            
        except Exception as e:
            logger.warning(f"Pagination handling failed: {e}")
            return False
    
    async def _click_load_more_buttons(self, page: Page):
        """Look for and click 'Load More' type buttons"""
        try:
            load_more_selectors = [
                'button:has-text("Load more")',
                'button:has-text("Show more")',
                'button:has-text("View more")',
                'button:has-text("See more")',
                'button[class*="load"]',
                'button[class*="more"]',
                '[data-testid*="load"]',
                '[data-testid*="more"]',
                'a:has-text("Load more")',
                'div[role="button"]:has-text("more")'
            ]
            
            for selector in load_more_selectors:
                try:
                    elements = await page.query_selector_all(selector)
                    for element in elements:
                        is_visible = await element.is_visible()
                        is_enabled = await element.is_enabled()
                        
                        if is_visible and is_enabled:
                            logger.info(f"Clicking load more button: {selector}")
                            await element.click()
                            await page.wait_for_timeout(2000)
                            break  # Only click one button per iteration
                            
                except Exception as e:
                    continue
                    
        except Exception as e:
            logger.warning(f"Load more button clicking failed: {e}")
    
    async def _count_content_items(self, page: Page) -> int:
        """Count content items to detect when new content loads"""
        try:
            # Try various selectors that might represent content items
            item_selectors = [
                '[data-testid*="item"]',
                '[data-testid*="card"]',
                '[class*="item"]',
                '[class*="card"]',
                '[class*="entry"]',
                '[class*="post"]',
                '[class*="listing"]',
                'article',
                '.item',
                '.card',
                '.entry',
                '.post',
                '.listing',
                'li[class*="item"]',
                'div[class*="row"]'
            ]
            
            max_count = 0
            
            for selector in item_selectors:
                try:
                    count = await page.evaluate(f'document.querySelectorAll("{selector}").length')
                    max_count = max(max_count, count)
                except:
                    continue
            
            # Fallback: count all divs if no specific items found
            if max_count < 5:
                max_count = await page.evaluate('document.querySelectorAll("div").length')
            
            return max_count
            
        except Exception as e:
            logger.warning(f"Item counting failed: {e}")
            return 0
    
    async def __aenter__(self):
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.cleanup()