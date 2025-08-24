import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
import pandas as pd
import io
from datetime import datetime

def send_predictions_email(df, recipient_emails, sender_email, sender_password, 
                          subject=None, body=None, attachment_name=None):
    """
    Send predictions DataFrame as CSV attachment via email to multiple recipients
    
    Args:
        df: pandas DataFrame with predictions
        recipient_emails: single email string or list of email addresses
        sender_email: your email address
        sender_password: your email password or app password
        subject: email subject (optional)
        body: email body text (optional)
        attachment_name: name for CSV file (optional)
    """
    
    # Handle both single email string and list of emails
    if isinstance(recipient_emails, str):
        recipient_list = [recipient_emails]
    else:
        recipient_list = recipient_emails
    
    # Default values
    if subject is None:
        subject = f"Apartment Rent Predictions - {datetime.now().strftime('%Y-%m-%d')}"
    
    if body is None:
        body = f"""
        Hi,
        
        Please find attached the apartment rent predictions generated on {datetime.now().strftime('%Y-%m-%d %H:%M')}.
        
        Summary:
        - Total predictions: {len(df)}
        - Average predicted rent: ${df['price_preds'].mean():.2f} (assuming 'predictions' column)
        
        Best regards
        """
    
    if attachment_name is None:
        attachment_name = f"rent_predictions_{datetime.now().strftime('%Y%m%d_%H%M')}.csv"
    
    # Create message
    msg = MIMEMultipart()
    msg['From'] = sender_email
    msg['To'] = ', '.join(recipient_list)  # Join multiple recipients with comma
    msg['Subject'] = subject
    
    # Add body to email
    msg.attach(MIMEText(body, 'plain'))
    
    # Convert DataFrame to CSV in memory
    csv_buffer = io.StringIO()
    df.to_csv(csv_buffer, index=False)
    csv_data = csv_buffer.getvalue()
    
    # Create attachment
    attachment = MIMEBase('application', 'octet-stream')
    attachment.set_payload(csv_data.encode('utf-8'))
    encoders.encode_base64(attachment)
    attachment.add_header(
        'Content-Disposition',
        f'attachment; filename= {attachment_name}'
    )
    
    # Attach the file to message
    msg.attach(attachment)
    
    # Gmail SMTP configuration (adjust for other email providers)
    try:
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()  # Enable encryption
        server.login(sender_email, sender_password)
        
        text = msg.as_string()
        server.sendmail(sender_email, recipient_list, text)  # Use recipient_list here
        server.quit()
        
        print(f"✓ Email sent successfully to {len(recipient_list)} recipient(s):")
        for email in recipient_list:
            print(f"  - {email}")
        print(f"  Attachment: {attachment_name}")
        print(f"  Records sent: {len(df)}")
        
    except Exception as e:
        print(f"✗ Failed to send email: {str(e)}")

# Alternative: Send as Excel file
def send_predictions_excel(df, recipient_email, sender_email, sender_password,
                          subject=None, body=None, attachment_name=None):
    """
    Send predictions DataFrame as Excel attachment via email
    """
    
    if attachment_name is None:
        attachment_name = f"rent_predictions_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx"
    
    # Create Excel file in memory
    excel_buffer = io.BytesIO()
    with pd.ExcelWriter(excel_buffer, engine='openpyxl') as writer:
        df.to_excel(writer, sheet_name='Predictions', index=False)
        
        # Optional: Add a summary sheet
        summary_df = pd.DataFrame({
            'Metric': ['Total Predictions', 'Average Rent', 'Min Rent', 'Max Rent'],
            'Value': [
                len(df),
                f"${df['predictions'].mean():.2f}" if 'predictions' in df.columns else 'N/A',
                f"${df['predictions'].min():.2f}" if 'predictions' in df.columns else 'N/A',
                f"${df['predictions'].max():.2f}" if 'predictions' in df.columns else 'N/A'
            ]
        })
        summary_df.to_excel(writer, sheet_name='Summary', index=False)
    
    excel_data = excel_buffer.getvalue()
    
    # Create message (similar to CSV version)
    msg = MIMEMultipart()
    msg['From'] = sender_email
    msg['To'] = recipient_email
    msg['Subject'] = subject or f"Apartment Rent Predictions - {datetime.now().strftime('%Y-%m-%d')}"
    
    body = body or f"""
    Hi,
    
    Please find attached the apartment rent predictions in Excel format.
    
    The file contains:
    - Predictions sheet: All prediction data
    - Summary sheet: Key statistics
    
    Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M')}
    
    Best regards
    """
    
    msg.attach(MIMEText(body, 'plain'))
    
    # Create Excel attachment
    attachment = MIMEBase('application', 'vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    attachment.set_payload(excel_data)
    encoders.encode_base64(attachment)
    attachment.add_header(
        'Content-Disposition',
        f'attachment; filename= {attachment_name}'
    )
    
    msg.attach(attachment)
    
    # Send email
    try:
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(sender_email, sender_password)
        
        text = msg.as_string()
        server.sendmail(sender_email, recipient_email, text)
        server.quit()
        
        print(f"✓ Excel file sent successfully to {recipient_email}")
        
    except Exception as e:
        print(f"✗ Failed to send email: {str(e)}")

# Usage examples:

# # Option 1: Send as CSV
# send_predictions_email(
#     df=df,
#     recipient_email="recipient@example.com",
#     sender_email="your_email@gmail.com",
#     sender_password="your_app_password",  # Use app password for Gmail
#     subject="Latest Apartment Rent Predictions",
#     body="Please find the latest predictions attached."
# )

# # Option 2: Send as Excel with multiple sheets
# send_predictions_excel(
#     df=df,
#     recipient_email="recipient@example.com", 
#     sender_email="your_email@gmail.com",
#     sender_password="your_app_password"
# )

# # Option 3: Send to multiple recipients
# recipients = ["person1@example.com", "person2@example.com", "person3@example.com"]

# for recipient in recipients:
#     send_predictions_email(
#         df=df,
#         recipient_email=recipient,
#         sender_email="your_email@gmail.com",
#         sender_password="your_app_password"
#     )
    
# Option 4: Quick one-liner for CSV
def quick_send_csv(df, to_email, from_email, password):
    send_predictions_email(df, to_email, from_email, password)

# Usage: quick_send_csv(df, "recipient@example.com", "sender@gmail.com", "password")