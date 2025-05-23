import logging
import re
from bs4 import BeautifulSoup
import hashlib
from datetime import datetime
import traceback

class ImprovedZipRecruiterScraper:
    def extract_job_listings(self, html_content, country_code):
        """Extract job listings from HTML content."""
        logging.info(f"Extracting job listings for country: {country_code}")
        logging.debug(f"HTML preview: {html_content[:1000]}")
        
        # Multiple selectors to try for job cards
        job_card_selectors = [
            '.job_content', '.job_result', '.jobList-item', '.job-card',
            'article.job_item', 'div[data-job-id]', '[class*="job_"]',
            '[data-testid="job-card"]', 'article', '.card'
        ]
        
        job_cards = []
        for selector in job_card_selectors:
            try:
                cards = BeautifulSoup(html_content, 'html.parser').select(selector)
                if cards:
                    logging.info(f"Found {len(cards)} job cards using selector: {selector}")
                    job_cards = cards
                    break
            except Exception as e:
                logging.error(f"Error finding job cards with selector {selector}: {e}")
        
        if not job_cards:
            logging.warning("No job cards found with standard selectors, trying alternative approach")
            soup = BeautifulSoup(html_content, 'html.parser')
            # Look for job titles and work backwards to find potential job cards
            potential_titles = soup.select('h2, h3, a[href*="job"], a[href*="career"]')
            if potential_titles:
                logging.info(f"Found {len(potential_titles)} potential job titles")
                # Use the first few potential titles to find their parent elements which might be job cards
                for title_elem in potential_titles[:10]:
                    parent = title_elem.parent
                    for _ in range(3):  # Check up to 3 levels up
                        if parent and (parent.get('class') or parent.name == 'article' or parent.name == 'div'):
                            job_cards.append(parent)
                            break
                        if parent:
                            parent = parent.parent
        
        logging.info(f"Found {len(job_cards)} job cards")
        
        if job_cards and len(job_cards) > 0:
            first_card = job_cards[0]
            logging.debug(f"First job card classes: {first_card.get('class')}")
            logging.debug(f"First job card attributes: {first_card.attrs}")
            
            title_elem = first_card.select_one('h2, h3, a[href*="job"]')
            if title_elem:
                logging.debug(f"First job title element: {title_elem.text.strip()}")
        
        jobs = []
        for idx, job_card in enumerate(job_cards):
            try:
                logging.debug(f"Processing job card {idx+1}/{len(job_cards)}")
                
                # Skip sponsored or promoted job cards
                if job_card.select_one('[class*="sponsor"], [class*="promoted"]'):
                    logging.debug(f"Skipping sponsored/promoted job {idx+1}")
                    continue
                
                # Extract job title - try multiple selectors
                title_selectors = ['h2', 'h3', 'a[href*="job"] strong', 'a[href*="job"]', '.job-title', '.title']
                job_title = None
                for selector in title_selectors:
                    title_elem = job_card.select_one(selector)
                    if title_elem and title_elem.text.strip():
                        job_title = title_elem.text.strip()
                        logging.debug(f"Found job title with selector {selector}: {job_title}")
                        break
                
                if not job_title:
                    logging.debug(f"No job title found for job card {idx+1}, skipping")
                    continue
                
                # Extract job URL - try multiple approaches
                job_url = None
                url_selectors = ['a[href*="job"]', 'h2 a', 'h3 a', '.job-title a', '.title a']
                for selector in url_selectors:
                    url_elem = job_card.select_one(selector)
                    if url_elem and url_elem.get('href'):
                        job_url = url_elem['href']
                        logging.debug(f"Found job URL with selector {selector}: {job_url}")
                        break
                
                if not job_url:
                    logging.debug(f"No job URL found for job {job_title}, skipping")
                    continue
                
                # Ensure URL is absolute
                if not job_url.startswith('http'):
                    if job_url.startswith('/'):
                        job_url = f"{self.base_urls.get(country_code, 'https://www.ziprecruiter.com')}{job_url}"
                    else:
                        job_url = f"{self.base_urls.get(country_code, 'https://www.ziprecruiter.com')}/{job_url}"
                    logging.debug(f"Converted to absolute URL: {job_url}")
                
                # Generate unique job ID
                job_id = hashlib.md5(job_url.encode()).hexdigest()
                logging.debug(f"Generated job ID: {job_id}")
                
                # Create job dictionary with basic information
                job = {
                    "id": job_id,
                    "title": job_title,
                    "url": job_url,
                    "source": "ZipRecruiter",
                    "country": country_code,
                    "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                }
                
                # Extract company name
                company_selectors = ['.company_name', '.company', '[class*="company"]', '.hiring-company']
                for selector in company_selectors:
                    company_elem = job_card.select_one(selector)
                    if company_elem and company_elem.text.strip():
                        job["company"] = company_elem.text.strip()
                        break
                
                # Extract location
                location_selectors = ['.location', '[class*="location"]', '[class*="address"]', '.job-location']
                for selector in location_selectors:
                    location_elem = job_card.select_one(selector)
                    if location_elem and location_elem.text.strip():
                        job["location"] = location_elem.text.strip()
                        break
                
                # Extract job description snippet
                description_selectors = ['.job_snippet', '.description', '.snippet', '[class*="description"]']
                for selector in description_selectors:
                    desc_elem = job_card.select_one(selector)
                    if desc_elem and desc_elem.text.strip():
                        job["description"] = desc_elem.text.strip()
                        break
                
                # Extract salary information
                job["salary"] = self.extract_salary(job_card)
                
                # Extract job type (full-time, part-time, etc.)
                job_type_selectors = ['.job_type', '.employment_type', '[class*="type"]']
                for selector in job_type_selectors:
                    type_elem = job_card.select_one(selector)
                    if type_elem and type_elem.text.strip():
                        job["job_type"] = type_elem.text.strip()
                        break
                
                # Extract date posted
                date_selectors = ['.date', '[class*="posted"]', '.job-age', '.posted-date']
                for selector in date_selectors:
                    date_elem = job_card.select_one(selector)
                    if date_elem and date_elem.text.strip():
                        job["date_posted"] = date_elem.text.strip()
                        break
                
                logging.info(f"Successfully extracted job: {job_title}")
                jobs.append(job)
                
            except Exception as e:
                logging.error(f"Error extracting job data: {e}")
                logging.error(traceback.format_exc())
                continue
        
        return jobs

    def extract_salary(self, job_card):
        """
        Extract salary information from a job card.
        
        Args:
            job_card: BeautifulSoup element representing a job card
            
        Returns:
            Dictionary containing salary information or None if not found
        """
        logging.debug("Attempting to extract salary information")
        
        # List of possible selectors for salary information
        salary_selectors = [
            '.salary', '[class*="salary"]', '.compensation', '[class*="compensation"]',
            '.pay', '[class*="pay"]', '.wage', '[data-testid*="salary"]',
            '[class*="money"]', '[class*="amount"]', '.job_salary'
        ]
        
        salary_text = None
        
        # Try each selector until we find something
        for selector in salary_selectors:
            try:
                salary_elem = job_card.select_one(selector)
                if salary_elem and salary_elem.text.strip():
                    salary_text = salary_elem.text.strip()
                    logging.debug(f"Found salary with selector {selector}: {salary_text}")
                    break
            except Exception as e:
                logging.debug(f"Error finding salary with selector {selector}: {e}")
        
        # If no salary found with specific selectors, try to find it in the full text
        if not salary_text:
            try:
                # Look for salary patterns in the entire job card text
                full_text = job_card.get_text()
                
                # Common salary patterns
                patterns = [
                    r'£\s*\d+[,\d]*\s*(?:-\s*£\s*\d+[,\d]*)?(?:\s*(?:per|a|/)\s*(?:year|annum|month|hour|yr|pa|p\.a\.|p/a))?',
                    r'\$\s*\d+[,\d]*\s*(?:-\s*\$\s*\d+[,\d]*)?(?:\s*(?:per|a|/)\s*(?:year|annum|month|hour|yr|pa|p\.a\.|p/a))?',
                    r'€\s*\d+[,\d]*\s*(?:-\s*€\s*\d+[,\d]*)?(?:\s*(?:per|a|/)\s*(?:year|annum|month|hour|yr|pa|p\.a\.|p/a))?',
                    r'\d+[,\d]*\s*(?:-\s*\d+[,\d]*)?\s*(?:GBP|USD|EUR|pounds|euros|dollars)',
                    r'(?:salary|pay|compensation)[:\s]*[£$€]?\s*\d+[,\d]*\s*(?:-\s*[£$€]?\s*\d+[,\d]*)?'
                ]
                
                for pattern in patterns:
                    match = re.search(pattern, full_text, re.IGNORECASE)
                    if match:
                        salary_text = match.group(0).strip()
                        logging.debug(f"Found salary with regex pattern: {salary_text}")
                        break
            except Exception as e:
                logging.debug(f"Error finding salary in full text: {e}")
        
        if not salary_text:
            logging.debug("No salary information found")
            return None
        
        # Process the found salary text
        try:
            # Clean up the text
            salary_text = salary_text.replace('\n', ' ').replace('\t', ' ')
            salary_text = re.sub(r'\s+', ' ', salary_text).strip()
            
            # Initialize salary data dictionary
            salary_data = {
                "text": salary_text,
                "currency": None,
                "min": None,
                "max": None,
                "period": None,
                "is_range": False
            }
            
            # Extract currency
            currency_match = re.search(r'[£$€]|GBP|USD|EUR|pounds|euros|dollars', salary_text, re.IGNORECASE)
            if currency_match:
                currency = currency_match.group(0).upper()
                if currency == '£' or currency == 'POUNDS' or currency == 'GBP':
                    salary_data["currency"] = "GBP"
                elif currency == '$' or currency == 'DOLLARS' or currency == 'USD':
                    salary_data["currency"] = "USD"
                elif currency == '€' or currency == 'EUROS' or currency == 'EUR':
                    salary_data["currency"] = "EUR"
            
            # Extract salary period
            period_match = re.search(r'per\s+(year|annum|month|hour|day|week)|/(year|annum|month|hour|day|week)|p\.a\.|pa\b|yearly|monthly|hourly|annual', 
                               salary_text, re.IGNORECASE)
            if period_match:
                period = period_match.group(0).lower()
                if 'year' in period or 'annum' in period or 'pa' in period or 'p.a' in period or 'annual' in period:
                    salary_data["period"] = "yearly"
                elif 'month' in period:
                    salary_data["period"] = "monthly"
                elif 'hour' in period:
                    salary_data["period"] = "hourly"
                elif 'day' in period:
                    salary_data["period"] = "daily"
                elif 'week' in period:
                    salary_data["period"] = "weekly"
            
            # Extract salary values
            numbers = re.findall(r'\d+[,\d]*(?:\.\d+)?', salary_text)
            if numbers:
                # Clean and convert numbers
                cleaned_numbers = [float(n.replace(',', '')) for n in numbers]
                
                # Check if it's a range
                if len(cleaned_numbers) >= 2:
                    salary_data["is_range"] = True
                    salary_data["min"] = min(cleaned_numbers)
                    salary_data["max"] = max(cleaned_numbers)
                else:
                    salary_data["min"] = cleaned_numbers[0]
            
            logging.debug(f"Extracted salary data: {salary_data}")
            return salary_data
            
        except Exception as e:
            logging.error(f"Error processing salary text '{salary_text}': {e}")
            return {"text": salary_text}  # Return just the raw text if processing fails 