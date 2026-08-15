"""
legacy/ — older modules kept for reference but no longer imported.

- sheets_google.py: original Google Sheets CRM (requires Google Cloud
  service account, which requires a credit card for new accounts).
  Replaced by notion_crm.py which is no-card-required.

- resend_client_legacy.py: original single-provider Resend client.
  Replaced by outreach/email_providers.py which adds Brevo & MailerSend
  as fallbacks for the 100 emails/day Resend cap.

Don't import anything from here in the main bot flow.
"""
