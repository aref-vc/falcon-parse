import os
import json
import logging
from typing import Dict, Any, List, Optional
import google.generativeai as genai
from google.generativeai.types import HarmCategory, HarmBlockThreshold
import asyncio
import time

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class GeminiClient:
    def __init__(self):
        self.api_key = os.getenv('GEMINI_API_KEY')
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY environment variable is required")
        
        # Configure Gemini
        genai.configure(api_key=self.api_key)
        
        # Initialize the model
        self.model = genai.GenerativeModel(
            model_name='gemini-1.5-flash',
            generation_config={
                'temperature': 0.1,
                'top_p': 0.8,
                'top_k': 40,
                'max_output_tokens': 4096,
            },
            safety_settings={
                HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
                HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
                HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
                HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
            }
        )
        
        # Rate limiting
        self.last_request_time = 0
        self.min_request_interval = 1.0  # Minimum 1 second between requests
        
    async def test_connection(self) -> bool:
        """Test the Gemini API connection"""
        try:
            response = self.model.generate_content("Test connection")
            return True
        except Exception as e:
            logger.error(f"Gemini API test failed: {e}")
            return False
    
    async def extract_data(self, scraped_content: Dict[str, Any], data_type: str, custom_instructions: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Extract structured data from scraped content using Gemini AI
        """
        logger.info(f"Extracting data type: {data_type}")
        
        # Apply rate limiting
        await self._apply_rate_limit()
        
        # Prepare the content for analysis
        text_content = scraped_content.get('text', '')
        page_title = scraped_content.get('title', '')
        social_links = scraped_content.get('social_links', {})
        emails = scraped_content.get('emails', [])
        
        # Truncate content if too long (Gemini has token limits)
        max_chars = 18000  # Leave room for social/email data
        if len(text_content) > max_chars:
            text_content = text_content[:max_chars] + "..."
            logger.warning(f"Content truncated to {max_chars} characters")
        
        # Build the extraction prompt
        prompt = self._build_extraction_prompt(
            text_content, 
            page_title, 
            data_type, 
            custom_instructions,
            social_links,
            emails
        )
        
        try:
            # Generate response
            response = self.model.generate_content(prompt)
            
            if not response.text:
                raise Exception("Empty response from Gemini API")
            
            # Parse the JSON response
            extracted_data = self._parse_gemini_response(response.text)
            
            logger.info(f"Successfully extracted {len(extracted_data)} items")
            return extracted_data
            
        except Exception as e:
            logger.error(f"Data extraction failed: {e}")
            raise Exception(f"Gemini AI extraction failed: {str(e)}")
    
    def _build_extraction_prompt(self, content: str, title: str, data_type: str, custom_instructions: Optional[str], social_links: Dict = None, emails: List = None) -> str:
        """Build the prompt for data extraction"""
        
        base_prompt = f"""
You are a professional data extraction specialist. Your task is to analyze the following web page content and extract structured data.

PAGE INFORMATION:
Title: {title}
Content: {content}

EXTRACTED CONTACT DATA:
Social Links Found: {social_links or {}}
Email Addresses Found: {emails or []}
(Note: {len(emails or [])} email addresses were pre-extracted from the HTML)

EXTRACTION TASK:
Extract: {data_type}

INSTRUCTIONS:
1. Analyze the content carefully and identify all relevant {data_type} information
2. Look for social media links, email addresses, and contact information in ALL formats (mailto:, @, linkedin.com, twitter.com, x.com, etc.)
3. Search for partially hidden or encoded contact information (like "name [at] domain [dot] com")
4. Check for social media handles, usernames, and profile URLs
5. Extract the data in a structured format
6. Return ONLY a valid JSON array of objects
7. Each object should have consistent field names across all items
8. Use these EXACT field names when available: "name", "title", "company", "email", "linkedin", "twitter", "phone"
9. Use descriptive but concise field names for other data
10. If a field is not available, use null instead of omitting it
11. Maintain the SAME FIELD ORDER in every object for consistency
12. Ensure all extracted data is accurate and comes directly from the content
13. Do not include any explanation or additional text - ONLY the JSON array

SPECIAL ATTENTION FOR CONTACT/SOCIAL DATA:
- Look for email patterns in ALL forms: username@domain.com, mailto: links, encoded emails
- Find obfuscated emails: "name at domain dot com", "name[at]domain[dot]com", "name (at) domain (dot) com"
- Search contact information in text content, even if partially hidden or formatted unusually
- Find LinkedIn profiles: linkedin.com/in/username, /company/name, or just "LinkedIn: username"  
- Detect Twitter/X handles: @username, twitter.com/username, x.com/username
- Search for other social platforms: facebook, instagram, github, etc.
- Check footer sections, contact pages, team sections, and about pages
- Look in metadata, alt text, and link titles
- Pay special attention to any text that might contain contact information
- If you see names but no emails, look harder in surrounding text for email patterns

EMAIL EXTRACTION PRIORITY:
- ALWAYS include email field even if empty/null
- Look for emails near person names in the content
- Check if emails are mentioned separately from names in lists or tables
- Search thoroughly for any email-like patterns in the entire content
- If no emails found in pre-extracted data, search manually in the content text
- Look for patterns like "contact:", "email:", "reach out:", "@", ".com", ".org", etc.
- Check for emails that might be written as text rather than links

"""

        # Add custom instructions if provided
        if custom_instructions:
            base_prompt += f"""
ADDITIONAL INSTRUCTIONS:
{custom_instructions}

"""

        # Add specific examples based on data type
        examples = self._get_extraction_examples(data_type)
        if examples:
            base_prompt += f"""
EXPECTED OUTPUT FORMAT EXAMPLE:
{examples}

"""

        base_prompt += """
IMPORTANT: Return ONLY the JSON array, no other text, explanations, or markdown formatting.
"""

        return base_prompt
    
    def _get_extraction_examples(self, data_type: str) -> str:
        """Get example output format for different data types"""
        data_type_lower = data_type.lower()
        
        if any(word in data_type_lower for word in ['product', 'item', 'catalog']):
            return '''[
  {
    "name": "Product Name",
    "price": "29.99",
    "description": "Product description",
    "availability": "In Stock",
    "brand": "Brand Name"
  }
]'''
        
        elif any(word in data_type_lower for word in ['contact', 'people', 'staff', 'team']):
            return '''[
  {
    "name": "John Smith",
    "title": "CEO",
    "email": "john@company.com",
    "phone": "+1-555-0123",
    "linkedin": "https://linkedin.com/in/johnsmith",
    "twitter": "@johnsmith",
    "instagram": "johnsmith_official",
    "facebook": "https://facebook.com/johnsmith",
    "github": "johnsmith-dev",
    "website": "https://johnsmith.com",
    "department": "Executive",
    "company": "Tech Corp"
  }
]'''
        
        elif any(word in data_type_lower for word in ['event', 'meeting', 'schedule']):
            return '''[
  {
    "title": "Event Title",
    "date": "2024-03-15",
    "time": "2:00 PM",
    "location": "Conference Room A",
    "description": "Event description"
  }
]'''
        
        elif any(word in data_type_lower for word in ['news', 'article', 'blog', 'post']):
            return '''[
  {
    "title": "Article Title",
    "author": "Author Name",
    "date": "2024-03-15",
    "category": "Technology",
    "summary": "Article summary",
    "url": "https://example.com/article"
  }
]'''
        
        elif any(word in data_type_lower for word in ['job', 'position', 'career']):
            return '''[
  {
    "title": "Software Engineer",
    "company": "Tech Corp",
    "location": "New York, NY",
    "type": "Full-time",
    "salary": "$80,000 - $120,000",
    "requirements": "5+ years experience"
  }
]'''
        
        elif any(word in data_type_lower for word in ['social', 'link', 'media', 'profile']):
            return '''[
  {
    "platform": "LinkedIn",
    "url": "https://linkedin.com/company/techcorp",
    "username": "techcorp",
    "followers": "10K",
    "verified": true
  },
  {
    "platform": "Twitter",
    "url": "https://twitter.com/techcorp",
    "username": "@techcorp",
    "followers": "5.2K",
    "verified": false
  }
]'''
        
        else:
            # Generic example
            return '''[
  {
    "field1": "value1",
    "field2": "value2",
    "field3": "value3"
  }
]'''
    
    def _parse_gemini_response(self, response_text: str) -> List[Dict[str, Any]]:
        """Parse and validate Gemini's JSON response"""
        try:
            # Clean the response text
            response_text = response_text.strip()
            
            # Remove markdown code blocks if present
            if response_text.startswith('```'):
                lines = response_text.split('\n')
                # Remove first and last lines (markdown delimiters)
                response_text = '\n'.join(lines[1:-1])
                response_text = response_text.strip()
            
            # Remove any leading/trailing non-JSON text
            start_idx = response_text.find('[')
            end_idx = response_text.rfind(']') + 1
            
            if start_idx != -1 and end_idx != 0:
                response_text = response_text[start_idx:end_idx]
            
            # Parse JSON
            data = json.loads(response_text)
            
            # Ensure it's a list
            if not isinstance(data, list):
                if isinstance(data, dict):
                    data = [data]
                else:
                    raise ValueError("Response is not a list or dictionary")
            
            # Validate each item is a dictionary
            for i, item in enumerate(data):
                if not isinstance(item, dict):
                    logger.warning(f"Item {i} is not a dictionary: {item}")
                    continue
            
            return [item for item in data if isinstance(item, dict)]
            
        except json.JSONDecodeError as e:
            logger.error(f"JSON parsing failed: {e}")
            logger.error(f"Response text: {response_text[:500]}...")
            
            # Fallback: try to extract any JSON-like structures
            return self._extract_fallback_data(response_text)
        
        except Exception as e:
            logger.error(f"Response parsing failed: {e}")
            raise Exception(f"Failed to parse Gemini response: {str(e)}")
    
    def _extract_fallback_data(self, text: str) -> List[Dict[str, Any]]:
        """Fallback method to extract data when JSON parsing fails"""
        try:
            # Try to find JSON objects in the text
            import re
            
            # Look for JSON-like patterns
            json_pattern = r'\{[^{}]*\}'
            matches = re.findall(json_pattern, text)
            
            extracted_items = []
            for match in matches:
                try:
                    item = json.loads(match)
                    if isinstance(item, dict):
                        extracted_items.append(item)
                except:
                    continue
            
            if extracted_items:
                logger.info(f"Fallback extraction found {len(extracted_items)} items")
                return extracted_items
            
            # If no JSON found, return a simple text extraction
            return [{
                "content": text[:500],
                "extraction_method": "fallback_text",
                "note": "Could not parse structured data"
            }]
            
        except Exception as e:
            logger.error(f"Fallback extraction failed: {e}")
            return [{
                "error": "Extraction failed",
                "raw_response": text[:200] + "..." if len(text) > 200 else text
            }]
    
    async def _apply_rate_limit(self):
        """Apply rate limiting to prevent API abuse"""
        current_time = time.time()
        time_since_last = current_time - self.last_request_time
        
        if time_since_last < self.min_request_interval:
            sleep_time = self.min_request_interval - time_since_last
            logger.info(f"Rate limiting: waiting {sleep_time:.2f} seconds")
            await asyncio.sleep(sleep_time)
        
        self.last_request_time = time.time()