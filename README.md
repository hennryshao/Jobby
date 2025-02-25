# Jobby - LinkedIn Job Scraper

Jobby is a web application that scrapes job listings from LinkedIn based on user-defined search criteria. It uses Playwright for browser automation and Bright Data for proxy services to reliably extract job information.

## Features

- Search for jobs by title, location, experience level, job type, and date posted
- Support for both English and French job titles
- Robust job data extraction with fallback mechanisms
- Clean and intuitive user interface
- Detailed logging for debugging

## Technologies Used

- **Backend**: Python, FastAPI, Playwright
- **Frontend**: HTML, CSS, JavaScript, Bootstrap 5
- **Proxy Service**: Bright Data Scraping Browser

## Setup and Installation

1. Clone the repository
2. Install the required Python packages:
   ```
   pip install fastapi uvicorn playwright
   ```
3. Install Playwright browsers:
   ```
   python -m playwright install
   ```
4. Set up your Bright Data credentials in the app.py file
5. Run the application:
   ```
   python app.py
   ```
6. Serve the frontend:
   ```
   python -m http.server 8080
   ```
7. Access the application at http://localhost:8080

## Usage

1. Enter a job title and location in the search form
2. Optionally select experience level, job type, and date posted filters
3. Check "Include French job titles" if searching in French-speaking regions
4. Click the "Search Jobs" button
5. View the search results with job details and links to apply

## License

This project is licensed under the MIT License - see the LICENSE file for details.
