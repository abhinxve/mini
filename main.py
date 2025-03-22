import time
from datetime import datetime
from auth import get_gmail_service
from utils import get_email_body, is_job_related, summarize_email, send_notification
import schedule

def process_emails():
    """Fetch and process new emails from Gmail."""
    # Authenticate with Gmail API
    service = get_gmail_service()
    
    # Read the last run timestamp to fetch only new emails
    try:
        with open('last_run.txt', 'r') as f:
            last_run = f.read().strip()
    except FileNotFoundError:
        last_run = None
    
    # Construct query to fetch emails since the last run
    query = f'after:{last_run}' if last_run else ''
    results = service.users().messages().list(userId='me', q=query).execute()
    messages = results.get('messages', [])
    
    print(f"Found {len(messages)} new emails.")
    
    # Process each email
    for msg in messages:
        msg_data = service.users().messages().get(userId='me', id=msg['id']).execute()
        email_text = get_email_body(msg_data['payload'])
        
        # Ensure email_text is valid before processing
        if email_text and is_job_related(email_text):
            summary = summarize_email(email_text)
            send_notification('New Job Email', summary)
            print(f"Job email found: {summary}")
    
    # Update the last run timestamp
    with open('last_run.txt', 'w') as f:
        f.write(str(int(time.time())))

def run_scheduler():
    """Schedule the email processing to run every 10 minutes."""
    schedule.every(10).minutes.do(process_emails)
    while True:
        schedule.run_pending()
        time.sleep(1)

if __name__ == '__main__':
    print("Starting job email filter...")
    process_emails()  # Run once immediately
    run_scheduler()   # Then run on a schedule