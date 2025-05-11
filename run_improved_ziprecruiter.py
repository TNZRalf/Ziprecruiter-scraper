#!/usr/bin/env python3
"""
Runner for Improved ZipRecruiter Scraper with UK/Europe Focus
"""
import os
import sys
import json
import time
import logging
import argparse
from datetime import datetime
import re
from bs4 import BeautifulSoup

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("ziprecruiter_runner.log"),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("ZipRecruiterRunner")

# Import our improved scraper
try:
    from improved_ziprecruiter_scraper import ImprovedZipRecruiterScraper
    logger.info("Successfully imported ImprovedZipRecruiterScraper")
except ImportError as e:
    logger.error(f"Error importing improved scraper: {e}")
    sys.exit(1)

def export_to_csv(jobs, filename):
    """Export jobs to CSV format"""
    try:
        import csv
        
        # Define CSV headers using LinkedIn's format
        headers = [
            'title', 'company', 'location', 'url', 'salary', 'description',
            'date_posted', 'date_posted_iso', 'is_remote', 'is_uk', 'is_europe', 
            'region', 'country_code', 'source', 'job_id', 'source_id', 'id',
            'job_type', 'standardized_job_type', 'experience', 'skills',
            'structured_description'
        ]
        
        with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=headers, extrasaction='ignore')
            writer.writeheader()
            writer.writerows(jobs)
                
        logger.info(f"Exported {len(jobs)} jobs to CSV file: {filename}")
        
    except Exception as e:
        logger.error(f"Error exporting to CSV: {e}")
        logger.exception("Exception details:")

def main():
    """Main entry point"""
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="Run Improved ZipRecruiter Scraper")
    parser.add_argument("--job-type", nargs='?', const="", default="software developer", help="Job type to search for (empty string for all jobs)")
    parser.add_argument("--location", default="Remote", help="Location to search in")
    parser.add_argument("--countries", default="uk,de,fr", help="Comma-separated list of country codes")
    parser.add_argument("--pages", type=int, default=2, help="Number of pages per country")
    parser.add_argument("--headless", action="store_true", default=True, help="Run in headless mode")
    parser.add_argument("--no-headless", action="store_false", dest="headless", help="Don't run in headless mode")
    parser.add_argument("--focus-europe", action="store_true", default=True, help="Focus on UK and Europe")
    parser.add_argument("--output", default=None, help="Output file (default: auto-generated)")
    parser.add_argument("--no-database", action="store_true", help="Don't use database")
    
    args = parser.parse_args()
    
    # Handle empty job type - either empty string or None
    if args.job_type is None or args.job_type.strip() == "":
        logger.warning("Empty job type provided. Using default 'all jobs'")
        args.job_type = "all jobs"
    
    # Generate output filename if not provided
    if args.output is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_job_type = args.job_type.replace(" ", "_")
        safe_location = args.location.replace(" ", "_")
        args.output = f"ziprecruiter_jobs_{safe_job_type}_{safe_location}_{timestamp}.json"
    
    # Parse countries
    country_codes = args.countries.split(",") if "," in args.countries else [args.countries]
    
    logger.info(f"Starting ZipRecruiter scraper for '{args.job_type}' in '{args.location}'")
    logger.info(f"Targeting countries: {', '.join(country_codes)}")
    
    try:
        # Initialize the scraper
        scraper = ImprovedZipRecruiterScraper(
            headless=args.headless,
            pages_per_search=args.pages,
            focus_on_uk_europe=args.focus_europe
        )
        
        # Start scraping
        start_time = time.time()
        jobs = scraper.scrape(args.job_type, args.location, country_codes)
        end_time = time.time()
        
        # Post-process to match LinkedIn's data structure
        jobs = post_process_job_data(jobs)
        
        # Calculate duration
        duration = end_time - start_time
        logger.info(f"Scraping completed in {duration:.2f} seconds")
        
        # Save results to JSON
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(jobs, f, indent=2, ensure_ascii=False)
        logger.info(f"Saved {len(jobs)} jobs to {args.output}")
        
        # Also save as CSV
        csv_file = args.output.replace(".json", ".csv")
        export_to_csv(jobs, csv_file)
        
        # Print summary
        print(f"\nScraping Summary:")
        print(f"Job Type: {args.job_type}")
        print(f"Location: {args.location}")
        print(f"Countries: {', '.join(country_codes)}")
        print(f"Total Jobs Found: {len(jobs)}")
        print(f"Duration: {duration:.2f} seconds")
        print(f"Results saved to: {args.output} and {csv_file}")
        
        # Analyze results by country
        country_stats = {}
        for job in jobs:
            country = job.get("country_code", "unknown")
            if country not in country_stats:
                country_stats[country] = 0
            country_stats[country] += 1
        
        print("\nJobs by Country:")
        for country, count in country_stats.items():
            print(f"  {country.upper()}: {count} jobs")
        
        return 0
    
    except Exception as e:
        logger.error(f"Error running scraper: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return 1

def post_process_job_data(jobs):
    """
    Post-process job data to fill in missing fields and normalize data
    
    Args:
        jobs: List of job dictionaries
        
    Returns:
        List of processed job dictionaries
    """
    logger.info("Post-processing job data")
    
    for job in jobs:
        # Process company information if missing or incomplete
        if not job.get("company") or job.get("company") == "Unknown Company" or job.get("company") == "":
            # Try to extract company from description
            if job.get("description"):
                desc = job.get("description")
                
                # Look for company patterns
                company_patterns = [
                    r"(?:at|for|with|by)\s+([A-Z][A-Za-z0-9\s&]+?(?:Ltd|Limited|Inc|LLC|GmbH|AG|plc|Co\.|Company)?)",
                    r"([A-Z][A-Za-z0-9\s&]+?(?:Ltd|Limited|Inc|LLC|GmbH|AG|plc|Co\.|Company)) is (?:seeking|looking|hiring)",
                    r"About\s+([A-Z][A-Za-z0-9\s&]+?(?:Ltd|Limited|Inc|LLC|GmbH|AG|plc|Co\.|Company))"
                ]
                
                for pattern in company_patterns:
                    match = re.search(pattern, desc)
                    if match:
                        possible_company = match.group(1).strip()
                        # Check if it's a reasonable company name
                        if 2 < len(possible_company) < 40 and not any(x in possible_company.lower() for x in ["apply", "role", "position", "job", "we are", "click", "ideal"]):
                            job["company"] = possible_company
                            break
            
            # If still no company, use generic name
            if not job.get("company") or job.get("company") == "Unknown Company" or job.get("company") == "":
                job["company"] = "Hiring Company"
        
        # Process location information if missing or incomplete
        if not job.get("location") or job.get("location") == "Unknown Location" or job.get("location") == "":
            # Default to UK for UK jobs
            if job.get("is_uk"):
                job["location"] = "United Kingdom - Remote"
            
            # Try to extract location from description
            if job.get("description"):
                desc = job.get("description")
                
                # Look for location patterns
                location_patterns = [
                    r"Location:\s*([A-Za-z\s,]+)",
                    r"(?:in|at|near|from)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)",
                    r"([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\s+(?:office|area|region)"
                ]
                
                for pattern in location_patterns:
                    match = re.search(pattern, desc)
                    if match:
                        possible_location = match.group(1).strip()
                        # Check if it's a reasonable location name
                        if 2 < len(possible_location) < 30 and not any(x in possible_location.lower() for x in ["salary", "about", "job", "position", "company"]):
                            job["location"] = possible_location
                            break
        
        # Clean and process description HTML if available
        if "description_html" in job:
            # Clean the HTML content
            clean_html = sanitize_html(job["description_html"])
            job["description_html"] = clean_html
            
            # Preserve formatted content for display
            job["formatted_description"] = format_html_to_text(clean_html)
        
        # Add structured_description (like LinkedIn does)
        if "description" in job:
            description = job["description"]
            # Use both text and HTML if available
            structured_description = structure_description(description, job.get("description_html", ""))
            if structured_description:
                job["structured_description"] = structured_description
                
        # Extract and standardize job type (like LinkedIn)
        if "job_type" in job:
            job_type_text = job["job_type"]
            standardized_job_type = extract_job_type(job_type_text, job.get("description", ""))
            job["standardized_job_type"] = standardized_job_type
        else:
            # Try to extract from description if job_type is missing
            standardized_job_type = extract_job_type(None, job.get("description", ""))
            if standardized_job_type:
                job["standardized_job_type"] = standardized_job_type
                job["job_type"] = standardized_job_type
                
        # Extract skills (similar to LinkedIn)
        if "description" in job:
            skills = extract_skills(job["description"])
            if skills:
                job["skills"] = skills
                
        # Extract experience requirement if available
        if "description" in job:
            experience = extract_experience(job["description"])
            if experience:
                job["experience"] = experience
                
    logger.info("Post-processing complete")
    return jobs

def sanitize_html(html_content):
    """
    Clean HTML content by removing scripts, styles, and unnecessary attributes
    
    Args:
        html_content: HTML content to clean
        
    Returns:
        Cleaned HTML content
    """
    if not html_content:
        return ""
        
    try:
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # Remove scripts and styles
        for script in soup(["script", "style"]):
            script.decompose()
        
        # Remove unnecessary attributes
        for tag in soup.recursiveChildGenerator():
            if hasattr(tag, 'attrs'):
                # Keep only essential attributes
                allowed_attrs = ['href', 'src', 'alt', 'title', 'class']
                attrs = dict(tag.attrs)
                for attr in attrs:
                    if attr not in allowed_attrs:
                        del tag.attrs[attr]
                        
                # Sanitize classes
                if 'class' in tag.attrs:
                    # Keep only classes that help with formatting
                    allowed_classes = ['list', 'item', 'heading', 'section', 'title', 'subtitle', 'bold', 'italic', 'underline']
                    tag['class'] = [c for c in tag['class'] if any(allowed in c.lower() for allowed in allowed_classes)]
                    if not tag['class']:
                        del tag['class']
        
        # Return the cleaned HTML
        return str(soup)
    except Exception as e:
        logger.warning(f"Error sanitizing HTML: {e}")
        return html_content

def format_html_to_text(html_content):
    """
    Format HTML content to preserve formatting in plain text
    
    Args:
        html_content: HTML content to format
        
    Returns:
        Formatted text with preserved structure
    """
    if not html_content:
        return ""
        
    try:
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # Format lists properly
        for ul in soup.find_all('ul'):
            for li in ul.find_all('li'):
                li_text = li.get_text().strip()
                # Replace list item with bullet point
                li.replace_with(f"• {li_text}\n")
        
        for ol in soup.find_all('ol'):
            for i, li in enumerate(ol.find_all('li'), 1):
                li_text = li.get_text().strip()
                # Replace list item with numbered point
                li.replace_with(f"{i}. {li_text}\n")
        
        # Format headings
        for heading in soup.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6']):
            heading_text = heading.get_text().strip()
            heading.replace_with(f"\n\n{heading_text}\n\n")
        
        # Format paragraphs
        for p in soup.find_all('p'):
            p_text = p.get_text().strip()
            p.replace_with(f"{p_text}\n\n")
        
        # Format line breaks
        for br in soup.find_all('br'):
            br.replace_with('\n')
        
        # Get text and normalize whitespace
        text = soup.get_text()
        text = re.sub(r'\n{3,}', '\n\n', text)  # Normalize multiple line breaks
        
        return text.strip()
    except Exception as e:
        logger.warning(f"Error formatting HTML to text: {e}")
        return BeautifulSoup(html_content, 'html.parser').get_text()

def structure_description(description_text, description_html=None):
    """
    Structure the job description into logical sections like LinkedIn does
    
    Args:
        description_text: Plain text description
        description_html: HTML description (optional)
        
    Returns:
        Dictionary with structured description sections
    """
    structured = {}
    
    try:
        # Common section headers to look for
        sections = {
            'about_company': ['about us', 'about the company', 'who we are', 'company overview', 'our company', 'company description'],
            'job_overview': ['job overview', 'position overview', 'role overview', 'about the job', 'about the role', 'job description', 'summary', 'overview'],
            'responsibilities': ['responsibilities', 'duties', 'what you\'ll do', 'your responsibilities', 'key responsibilities', 'role responsibilities', 'job duties', 'main duties', 'essential duties', 'the role', 'day to day', 'day-to-day'],
            'requirements': ['requirements', 'qualifications', 'what you need', 'skills', 'required skills', 'must have', 'experience required', 'required experience', 'essential skills', 'you will need', 'you\'ll need', 'we are looking for', 'ideal candidate', 'candidate profile', 'who you are'],
            'nice_to_have': ['nice to have', 'preferred', 'bonus points', 'plus', 'desirable', 'additional skills', 'preferred qualifications', 'preferred skills', 'good to have'],
            'benefits': ['benefits', 'perks', 'what we offer', 'compensation', 'package', 'salary', 'rewards', 'we provide', 'we offer', 'what\'s in it for you', 'what\'s on offer', 'what you\'ll get'],
            'application_process': ['application process', 'how to apply', 'next steps', 'apply', 'apply now', 'application procedure']
        }
        
        # First try to parse from HTML if available
        if description_html:
            soup = BeautifulSoup(description_html, 'html.parser')
            
            # Find all elements that could be headers (h1-h6, strong, b, etc.)
            potential_headers = soup.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'strong', 'b'])
            section_content = {}
            current_section = None
            
            # Check if we have potential headers
            if potential_headers:
                # Process each potential header
                for header in potential_headers:
                    header_text = header.get_text().strip().lower()
                    
                    # Skip empty or very long headers
                    if not header_text or len(header_text) > 50:
                        continue
                    
                    # Check if this header matches any of our sections
                    matched_section = None
                    for section_key, keywords in sections.items():
                        if any(keyword in header_text for keyword in keywords):
                            matched_section = section_key
                            break
                    
                    if matched_section:
                        # If we found a section header, get all content until the next header
                        content = []
                        next_element = header.next_sibling
                        
                        while next_element and next_element not in potential_headers:
                            if hasattr(next_element, 'get_text'):
                                text = next_element.get_text().strip()
                                if text:
                                    content.append(text)
                            elif isinstance(next_element, str) and next_element.strip():
                                content.append(next_element.strip())
                            
                            next_element = next_element.next_sibling if hasattr(next_element, 'next_sibling') else None
                        
                        if content:
                            section_content[matched_section] = '\n'.join(content)
                
                if section_content:
                    structured = section_content
        
        # If HTML parsing didn't yield results, fall back to text parsing
        if not structured:
            # Simple text-based parsing for short job descriptions
            lines = description_text.split('\n')
            current_section = None
            section_content = {}
            section_lines = []
            
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                    
                line_lower = line.lower()
                
                # Check if this line looks like a header
                matched_section = None
                for section_key, keywords in sections.items():
                    if any(keyword in line_lower for keyword in keywords):
                        # The line should be relatively short to be a header
                        if len(line) < 50:
                            matched_section = section_key
                            break
                
                if matched_section:
                    # If we were already collecting a section, save it
                    if current_section and section_lines:
                        section_content[current_section] = '\n'.join(section_lines)
                        
                    # Start new section
                    current_section = matched_section
                    section_lines = []
                elif current_section:
                    # Add to current section
                    section_lines.append(line)
            
            # Don't forget the last section
            if current_section and section_lines:
                section_content[current_section] = '\n'.join(section_lines)
                
            if section_content:
                structured = section_content
        
        # If we don't have much structure, try to identify common patterns
        if len(structured) < 2:
            # Try to identify bullet point sections
            bullet_sections = re.split(r'\n\s*•|\n\s*-|\n\s*\*|\n\s*\d+\.', description_text)
            if len(bullet_sections) > 3:  # If we have a decent number of bullet points
                # First part is usually about the company or role
                if len(bullet_sections[0]) > 100:
                    structured['about'] = bullet_sections[0].strip()
                
                # The bullet points themselves are likely requirements or responsibilities
                bullets = []
                for i in range(1, len(bullet_sections)):
                    if bullet_sections[i].strip():
                        bullets.append("• " + bullet_sections[i].strip())
                
                if bullets:
                    # Try to determine if these are requirements or responsibilities
                    bullets_text = ' '.join(bullets).lower()
                    
                    # More comprehensive keyword matching for requirements vs responsibilities
                    requirement_keywords = ['experience', 'skill', 'proficiency', 'knowledge', 'degree', 'qualification', 
                                           'background', 'ability', 'familiar', 'understanding', 'education',
                                           'proficient', 'competent', 'expertise', 'fluent', 'capable', 'able to',
                                           'bachelor', 'master', 'phd', 'certification', 'qualified']
                    
                    responsibility_keywords = ['responsible', 'duty', 'ensure', 'manage', 'develop', 'create', 
                                              'implement', 'deliver', 'coordinate', 'lead', 'organize', 'assist',
                                              'maintain', 'support', 'prepare', 'provide', 'handle', 'work with',
                                              'collaborate', 'participate', 'communicate', 'report', 'conduct']
                    
                    # Count keyword occurrences
                    req_count = sum(1 for keyword in requirement_keywords if keyword in bullets_text)
                    resp_count = sum(1 for keyword in responsibility_keywords if keyword in bullets_text)
                    
                    if req_count > resp_count:
                        structured['requirements'] = '\n'.join(bullets)
                    else:
                        structured['responsibilities'] = '\n'.join(bullets)
        
        # For very short descriptions, provide a simple structure
        if not structured and description_text:
            # If the description is short, just use it as the overview
            if len(description_text) < 500:
                structured['job_overview'] = description_text.strip()
            else:
                # Try to split into overview and requirements based on keyword analysis
                text_lower = description_text.lower()
                
                # Try to find logical breakpoints using patterns like numbered lists, dashes or bullet points
                sections_split = re.split(r'(\n\s*\d+\.|\n\s*•|\n\s*-|\n\s*\*|\n{2,})', description_text)
                
                # Clean up the split result
                clean_sections = []
                for i, section in enumerate(sections_split):
                    if section and not re.match(r'^\s*(\n\s*\d+\.|\n\s*•|\n\s*-|\n\s*\*|\n{2,})\s*$', section):
                        clean_sections.append(section.strip())
                
                if len(clean_sections) > 1:
                    # First section is typically the overview
                    structured['job_overview'] = clean_sections[0]
                    
                    # Analyze remaining sections to classify them
                    for i, section in enumerate(clean_sections[1:], 1):
                        section_lower = section.lower()
                        section_words = section_lower.split()
                        
                        # Skip very short sections
                        if len(section_words) < 10:
                            continue
                        
                        # Simple classification based on keyword presence
                        if any(word in section_lower for word in ['experience', 'skill', 'require', 'qualification', 'proficiency']):
                            structured['requirements'] = section
                        elif any(word in section_lower for word in ['responsible', 'duty', 'task', 'role', 'work on']):
                            structured['responsibilities'] = section
                        elif any(word in section_lower for word in ['benefit', 'offer', 'salary', 'compensation', 'package']):
                            structured['benefits'] = section
                        elif any(word in section_lower for word in ['company', 'about us', 'who we are']):
                            structured['about_company'] = section
                else:
                    structured['job_overview'] = description_text.strip()
        
        return structured
        
    except Exception as e:
        logger.warning(f"Error structuring description: {e}")
        # Provide a minimal structure even on error
        if description_text:
            return {"job_overview": description_text.strip()}
        return {}

def extract_job_type(job_type_text=None, description_text=None):
    """
    Extract standardized job type from the job type text or description (LinkedIn style)
    
    Args:
        job_type_text: Text describing the job type 
        description_text: Full job description text
        
    Returns:
        Standardized job type string
    """
    if not job_type_text and not description_text:
        return ""
    
    # Common job types and their variations
    job_type_patterns = {
        "Full-time": [
            r"full[- ]?time", r"full time", r"permanent", r"regular",
            r"ft\b", r"f/t\b", r"\bft\b", r"40\s?hours?", r"permanent", 
            r"regular", r"permanent full[- ]?time"
        ],
        "Part-time": [
            r"part[- ]?time", r"part time", r"\bpt\b", r"p/t\b", r"\bpt\b", 
            r"(\d{1,2})-(\d{1,2})\s?hours?", r"part-time permanent"
        ],
        "Contract": [
            r"contract", r"fixed[- ]?term", r"temporary", r"temp\b", 
            r"interim", r"non[- ]?permanent", r"\bltd\b", r"limited term"
        ],
        "Freelance": [
            r"freelance", r"self[- ]?employed", r"independent contractor",
            r"1099", r"gig"
        ],
        "Internship": [
            r"internship", r"intern\b", r"trainee", r"placement",
            r"student", r"co-op", r"apprentice"
        ],
        "Temporary": [
            r"temp\b", r"temporary", r"seasonal"
        ],
        "Volunteer": [
            r"volunteer", r"unpaid", r"pro bono"
        ]
    }
    
    # Check job_type_text first if available
    if job_type_text:
        job_type_text = job_type_text.lower()
        
        # Direct match on the job type text
        for standard_type, patterns in job_type_patterns.items():
            for pattern in patterns:
                if re.search(pattern, job_type_text, re.IGNORECASE):
                    return standard_type
    
    # If job type not found from job_type_text, try from description
    if description_text:
        description_text = description_text.lower()
        
        # Look for job type indicators in the description
        # First check for mentions near job type keywords
        job_type_contexts = re.findall(
            r"(employment|job|position|work)\s+type\s*:?\s*([^.,:;]+)", 
            description_text
        )
        
        # Check matches from contexts
        for _, context in job_type_contexts:
            for standard_type, patterns in job_type_patterns.items():
                for pattern in patterns:
                    if re.search(pattern, context, re.IGNORECASE):
                        return standard_type
        
        # If not found in specific contexts, search the entire description
        for standard_type, patterns in job_type_patterns.items():
            for pattern in patterns:
                if re.search(pattern, description_text, re.IGNORECASE):
                    return standard_type
    
    # Default to "Full-time" if no match found
    return "Full-time"  # Most professional jobs are full-time

def extract_skills(description):
    """
    Extract skills from job description (LinkedIn style)
    
    Args:
        description: Job description text
        
    Returns:
        List of skills
    """
    skills = []
    
    # List of common tech skills to check for
    common_skills = [
        "python", "javascript", "react", "angular", "vue", "node", "django", 
        "flask", "java", "c++", "c#", "ruby", "php", "sql", "postgresql", 
        "mysql", "mongodb", "aws", "azure", "gcp", "docker", "kubernetes",
        "git", "github", "agile", "scrum", "jira", "html", "css", "sass",
        "typescript", "redux", "express", "spring", "hibernate", "jquery",
        "graphql", "rest api", "microservices", "devops", "ci/cd",
        "tensorflow", "pytorch", "machine learning", "data science",
        "excel", "powerpoint", "word", "project management", "team leadership"
    ]
    
    description_lower = description.lower()
    
    # Check for each skill
    for skill in common_skills:
        if skill in description_lower:
            # For multi-word skills, make sure they're together
            if " " in skill:
                if re.search(r'\b' + re.escape(skill) + r'\b', description_lower):
                    skills.append(skill.title())  # Capitalize skill name
            else:
                skills.append(skill.title())  # Capitalize skill name
    
    return skills if skills else None

def extract_experience(description):
    """
    Extract experience requirement from job description
    
    Args:
        description: Job description text
        
    Returns:
        Experience requirement string or None
    """
    # Common patterns for experience requirements
    patterns = [
        r'(\d+(?:\+|\s*\+)?(?:\s*\-\s*\d+)?)\s*(?:years?|yrs?)(?:\s*of)?(?:\s*experience)?',
        r'experience:?\s*(\d+(?:\+|\s*\+)?(?:\s*\-\s*\d+)?)\s*(?:years?|yrs?)',
        r'minimum(?:\s*of)?\s*(\d+(?:\+|\s*\+)?(?:\s*\-\s*\d+)?)\s*(?:years?|yrs?)(?:\s*experience)?',
        r'at\s*least\s*(\d+(?:\+|\s*\+)?(?:\s*\-\s*\d+)?)\s*(?:years?|yrs?)(?:\s*experience)?'
    ]
    
    description_lower = description.lower()
    
    for pattern in patterns:
        match = re.search(pattern, description_lower)
        if match:
            experience = match.group(1).strip()
            context_start = max(0, match.start() - 30)
            context_end = min(len(description_lower), match.end() + 30)
            context = description_lower[context_start:context_end]
            
            # Format the experience text nicely
            if '-' in experience or 'to' in experience:
                return f"{experience} years of experience"
            else:
                return f"{experience}+ years of experience"
    
    return None

if __name__ == "__main__":
    sys.exit(main()) 