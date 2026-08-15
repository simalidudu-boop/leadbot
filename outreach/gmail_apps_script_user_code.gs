/**
 * Gmail-via-Apps-Script Webhook
 * ==============================
 * Deploy this as a Web App in Google Apps Script.
 * The Python bot POSTs to the Web App URL with JSON like:
 *   { "to": "...", "subject": "...", "body": "...", "attachments": [...] }
 * This script uses MailApp.sendEmail() to send from your Gmail account.
 *
 * Setup:
 * 1. Open https://script.google.com → "New project"
 * 2. Replace the empty Code.gs with everything below (from line 18 onwards)
 * 3. Click "Save" (Ctrl+S)
 * 4. Click "Deploy" → "New deployment"
 * 5. Click the gear icon → "Web app"
 * 6. Description: "Lead Bot"
 * 7. Execute as: Me
 * 8. Who has access: Anyone
 * 9. Click "Deploy"
 * 10. You'll be asked to authorize — click "Authorize access", pick your
 *     Google account, click "Advanced" → "Go to (project) (unsafe)" →
 *     "Allow"
 * 11. Copy the "Web app URL" (looks like:
 *     https://script.google.com/macros/s/AKfycb.../exec)
 * 12. Paste that URL as the GMAIL_WEBHOOK_URL env var in Railway
 */

function doPost(e) {
  try {
    var data = JSON.parse(e.postData.contents);

    var to = data.to;
    var subject = data.subject;
    var body = data.body;
    var htmlBody = data.htmlBody || null;
    var name = data.name || "";
    var fromName = data.fromName || "Lead Bot";

    if (!to || !subject || !body) {
      return ContentService.createTextOutput(JSON.stringify({
        status: "error",
        error: "missing required fields: to, subject, body"
      })).setMimeType(ContentService.MimeType.JSON);
    }

    // Build the email options
    var options = {
      name: fromName,
    };

    if (htmlBody) {
      options.htmlBody = htmlBody;
    }

    // Handle attachments (base64-encoded)
    if (data.attachments && Array.isArray(data.attachments)) {
      options.attachments = data.attachments.map(function (att) {
        return Utilities.newBlob(
          Utilities.base64Decode(att.content),
          att.mimeType || "application/octet-stream",
          att.filename
        );
      });
    }

    // Send! MailApp.sendEmail(to, subject, body, options) sends from
    // the authenticated user's Gmail account.
    MailApp.sendEmail(to, subject, body, options);

    return ContentService.createTextOutput(JSON.stringify({
      status: "sent",
      to: to,
      timestamp: new Date().toISOString()
    })).setMimeType(ContentService.MimeType.JSON);

  } catch (err) {
    return ContentService.createTextOutput(JSON.stringify({
      status: "error",
      error: err.toString()
    })).setMimeType(ContentService.MimeType.JSON);
  }
}

// Optional: a simple GET handler so you can test the deployment in a browser
function doGet(e) {
  return ContentService.createTextOutput(JSON.stringify({
    status: "ready",
    message: "POST JSON to this URL to send an email. See documentation."
  })).setMimeType(ContentService.MimeType.JSON);
}
