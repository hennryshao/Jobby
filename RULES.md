# Jobby - LinkedIn Job Search Project Rules

## 1. Project Core Logic
- job_scraper.py is the main component that handles all scraping logic
- User inputs (job title, location, filters) determine the LinkedIn search URL
- Bright Data's Scraping Browser service is used as a tool to assist the scraping process
- The system follows this flow:
  1. User provides search criteria
  2. job_scraper.py constructs LinkedIn URL
  3. job_scraper.py uses Bright Data's Scraping Browser to access LinkedIn
  4. job_scraper.py extracts and returns job information

## 2. Application Logic Flow
1. User Input Processing:
   - Receive job title and location (required)
   - Process optional filters if provided
   - Validate all inputs

2. URL Construction (job_scraper.py):
   - Base URL: https://www.linkedin.com/jobs/search
   - Add required parameters: keywords, location
   - Add filter parameters if present:
     * Experience: f_E parameter
     * Job Type: f_JT parameter
     * Date Posted: f_TPR parameter

3. Scraping Process (job_scraper.py + Bright Data):
   - job_scraper.py prepares the scraping logic
   - Connects to Bright Data Scraping Browser for assistance
   - Navigates to the constructed LinkedIn URL
   - Waits for job results to load
   - Extracts job information:
     * Job title
     * Company name
     * Location
     * Post date
     * Job URL

4. Error Handling:
   - Connection issues (407, 403, 503)
   - Page loading timeout
   - No results found
   - LinkedIn anti-scraping detection

## 3. User Input Parameters
- Job Title (Required): Used in LinkedIn search query
- Location (Required): Used in LinkedIn search query
- Optional Filters (Maps to LinkedIn URL parameters):
  - Experience Level:
    * Internship
    * Entry level
    * Associate
    * Mid-Senior level
    * Director
    * Executive
  
  - Job Type:
    * Full-time
    * Part-time
    * Contract
    * Temporary
    * Internship
    * Volunteer
    * Other
  
  - Date Posted:
    * Past 24 hours
    * Past week
    * Past month

## 4. Bright Data Integration
- Role: Supporting tool for job_scraper.py
- Purpose: 
  * Helps job_scraper.py bypass LinkedIn's anti-scraping mechanisms
  * Provides stable browser environment
  * Handles complex page interactions
- Configuration: Detailed in bright data-scraping browser.txt
- Authentication: Credentials stored in mine.txt
- Usage: job_scraper.py uses Bright Data's Scraping Browser API to:
  * Connect to a remote browser instance
  * Navigate web pages
  * Handle dynamic content
  * Manage sessions

## 5. Communication Rules
- User Interface: English
- Code and Files: English
- Communication with Developer: Chinese
- Always ask for confirmation before major changes
- Never modify UI/frontend code without explicit permission from developer

## 6. Error Handling
- Save screenshots for debugging
- Log errors in detail
- Show user-friendly error messages
- Handle network timeouts appropriately
