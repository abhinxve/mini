import spacy
from transformers import pipeline
import re
import base64
from bs4 import BeautifulSoup
from plyer import notification

# Load spaCy model for NER
nlp = spacy.load("en_core_web_sm")

# Load summarization pipeline with BART model
try:
    summarizer = pipeline("summarization", model="facebook/bart-large-cnn")
except RuntimeError as e:
    print(f"Error loading summarizer: {e}. Falling back to basic summarization.")
    summarizer = None

def get_email_body(payload):
    """Extract the email body from the payload."""
    if 'parts' in payload:
        for part in payload['parts']:
            if part['mimeType'] == 'text/plain' and 'data' in part['body']:
                return base64.urlsafe_b64decode(part['body']['data']).decode('utf-8')
            elif part['mimeType'] == 'text/html' and 'data' in part['body']:
                html = base64.urlsafe_b64decode(part['body']['data']).decode('utf-8')
                soup = BeautifulSoup(html, 'html.parser')
                return soup.get_text()
        return ''  # Return empty string if no text parts are found
    else:
        if 'body' in payload and 'data' in payload['body']:
            return base64.urlsafe_b64decode(payload['body']['data']).decode('utf-8')
        return ''  # Return empty string if no body data

def is_job_related(email_text):
    """Check if the email is job-related based on expanded keywords."""
    job_keywords = [
        'job', 'career', 'position', 'hiring', 'apply', 'interview', 'opportunity',
        'joining', 'role', 'manager', 'team', 'start', 'welcome'  # Added for announcements
    ]
    email_lower = email_text.lower()
    result = any(keyword in email_lower for keyword in job_keywords)
    print(f"Job-related check: {result} (Text: {email_lower[:100]}...)")  # Debugging
    return result

def extract_key_info(email_text):
    """Extract key job-related information using NER and regex."""
    doc = nlp(email_text)
    
    entities = {
        "company": [ent.text for ent in doc.ents if ent.label_ == "ORG"],
        "location": [ent.text for ent in doc.ents if ent.label_ == "GPE"],
        "date": [ent.text for ent in doc.ents if ent.label_ == "DATE"]
    }
    
    job_title_patterns = [r'\b(?:position|role|job)\s*:\s*([^\n]+)', r'\b(?:hiring for|joining as|looking for)\s*([^\n]+)']
    for pattern in job_title_patterns:
        match = re.search(pattern, email_text, re.IGNORECASE)
        if match:
            entities["job_title"] = match.group(1).strip()
            break
    
    salary_pattern = r'\b(?:salary|compensation)\s*:\s*\$?([\d,]+(?:-\d+,\d+)?)\b'
    salary_match = re.search(salary_pattern, email_text, re.IGNORECASE)
    if salary_match:
        entities["salary"] = salary_match.group(1)
    
    job_type_keywords = ['full-time', 'part-time', 'remote', 'contract', 'internship']
    for keyword in job_type_keywords:
        if keyword in email_text.lower():
            entities["job_type"] = keyword
            break
    
    link_pattern = r'(https?://[^\s]+)'
    link_match = re.search(link_pattern, email_text)
    if link_match:
        entities["application_link"] = link_match.group(0)
    
    return entities

def summarize_email(email_text):
    """Summarize the email with job-related details for job seekers."""
    if not email_text.strip():
        return "No content to summarize."
    
    key_info = extract_key_info(email_text)
    
    if summarizer:
        summary = summarizer(email_text, max_length=150, min_length=50, do_sample=False)[0]['summary_text']
    else:
        summary = email_text[:200] + '...' if len(email_text) > 200 else email_text
    
    structured_summary = "Job Opportunity Summary:\n"
    if "job_title" in key_info:
        structured_summary += f"Title: {key_info['job_title']}\n"
    if "company" in key_info and key_info["company"]:
        structured_summary += f"Company: {', '.join(key_info['company'])}\n"
    if "location" in key_info and key_info["location"]:
        structured_summary += f"Location: {', '.join(key_info['location'])}\n"
    if "date" in key_info and key_info["date"]:
        structured_summary += f"Start/Deadline: {', '.join(key_info['date'])}\n"
    if "salary" in key_info:
        structured_summary += f"Salary: ${key_info['salary']}\n"
    if "job_type" in key_info:
        structured_summary += f"Type: {key_info['job_type'].capitalize()}\n"
    if "application_link" in key_info:
        structured_summary += f"Apply Here: {key_info['application_link']}\n"
    structured_summary += f"\nDetails: {summary}"
    
    return structured_summary

def send_notification(title, message):
    """Send a desktop notification, truncating message if necessary for Windows."""
    MAX_MESSAGE_LENGTH = 256
    if len(message) > MAX_MESSAGE_LENGTH:
        truncated = ""
        for line in message.split('\n'):
            if "Title:" in line or "Company:" in line or "Deadline:" in line or "Apply Here:" in line:
                truncated += line + "\n"
            if len(truncated) >= MAX_MESSAGE_LENGTH - 20:
                break
        message = truncated.strip() + "..." if truncated else message[:MAX_MESSAGE_LENGTH - 3] + "..."
    
    notification.notify(
        title=title,
        message=message,
        app_name='Job Email Filter',
        timeout=10
    )
    print(f"Full Notification Content:\n{message}")