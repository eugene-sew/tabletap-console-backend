import os
import resend
from django.conf import settings

resend.api_key = settings.RESEND_API_KEY

def send_staff_invitation_email(email, first_name, role_name, tenant_name, frontend_url=None, invite_token=None):
    """
    Sends an invitation email to a newly invited staff member using Resend.
    """
    if not resend.api_key:
        print(f"Warning: RESEND_API_KEY is not set. Skipping email to {email}")
        return

    app_url = frontend_url or getattr(settings, 'FRONTEND_URL', 'https://tabletap.space')
    signup_url = f"{app_url}/auth/signup?invited=1"
    if invite_token:
        signup_url += f"&t={invite_token}"

    greeting = f"Hi {first_name}," if first_name else "Hello,"

    role_description = {
        'Owner': 'full administrative access to everything in the console',
        'Manager': 'management access including menus, orders, tables, team, and feedback',
        'Waiter': 'access to the POS system and order processing',
    }.get(role_name, f'access as {role_name}')

    html_content = f"""
<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
</head>
<body style="margin:0;padding:0;background-color:#f5f5f5;font-family:Arial,Helvetica,sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0" style="background-color:#f5f5f5;padding:40px 0;">
    <tr>
      <td align="center">
        <table width="600" cellpadding="0" cellspacing="0" style="background-color:#ffffff;border-radius:16px;overflow:hidden;box-shadow:0 4px 24px rgba(0,0,0,0.08);">

          <!-- Header -->
          <tr>
            <td style="background:linear-gradient(135deg,#F97315,#ea580c);padding:40px 48px;text-align:center;">
              <h1 style="margin:0;color:#ffffff;font-size:28px;font-weight:700;letter-spacing:-0.5px;">
                TableTap Console
              </h1>
              <p style="margin:8px 0 0;color:rgba(255,255,255,0.85);font-size:14px;">
                Restaurant Management Platform
              </p>
            </td>
          </tr>

          <!-- Body -->
          <tr>
            <td style="padding:48px;">
              <p style="margin:0 0 8px;font-size:16px;color:#374151;">{greeting}</p>
              <h2 style="margin:0 0 24px;font-size:24px;color:#111827;font-weight:600;">
                You&#39;re invited to join {tenant_name}
              </h2>
              <p style="margin:0 0 16px;font-size:15px;color:#6b7280;line-height:1.6;">
                <strong style="color:#111827;">{tenant_name}</strong> has invited you to their
                restaurant console as a <strong style="color:#F97315;">{role_name}</strong>.
              </p>
              <p style="margin:0 0 32px;font-size:15px;color:#6b7280;line-height:1.6;">
                Your role gives you {role_description}.
              </p>

              <!-- Credentials box -->
              <table width="100%" cellpadding="0" cellspacing="0"
                     style="background-color:#fff7ed;border:1px solid #fed7aa;border-radius:12px;margin-bottom:32px;">
                <tr>
                  <td style="padding:20px 24px;">
                    <p style="margin:0 0 8px;font-size:13px;font-weight:600;color:#9a3412;text-transform:uppercase;letter-spacing:0.05em;">
                      Your Login Details
                    </p>
                    <p style="margin:0 0 4px;font-size:14px;color:#374151;">
                      <strong>Email:</strong> {email}
                    </p>
                    <p style="margin:0;font-size:13px;color:#6b7280;">
                      Use this email to create your account. You&#39;ll set your own password during sign-up.
                    </p>
                  </td>
                </tr>
              </table>

              <!-- CTA Button -->
              <table width="100%" cellpadding="0" cellspacing="0">
                <tr>
                  <td align="center" style="padding-bottom:32px;">
                    <a href="{signup_url}"
                       style="display:inline-block;background-color:#F97315;color:#ffffff;text-decoration:none;
                              font-size:16px;font-weight:600;padding:14px 40px;border-radius:10px;
                              letter-spacing:0.01em;">
                      Create Your Account
                    </a>
                  </td>
                </tr>
              </table>

              <p style="margin:0;font-size:13px;color:#9ca3af;line-height:1.6;">
                If the button doesn&#39;t work, copy and paste this link into your browser:<br/>
                <a href="{signup_url}" style="color:#F97315;">{signup_url}</a>
              </p>
            </td>
          </tr>

          <!-- Footer -->
          <tr>
            <td style="background-color:#f9fafb;border-top:1px solid #e5e7eb;padding:24px 48px;text-align:center;">
              <p style="margin:0;font-size:12px;color:#9ca3af;">
                This invitation was sent by <strong>{tenant_name}</strong> via TableTap &mdash;
                Restaurant Management Platform.<br/>
                If you weren&#39;t expecting this email, you can safely ignore it.
              </p>
            </td>
          </tr>

        </table>
      </td>
    </tr>
  </table>
</body>
</html>
    """

    try:
        r = resend.Emails.send({
            "from": f"{tenant_name} via TableTap <noreply@tabletap.space>",
            "to": [email],
            "subject": f"You're invited to join {tenant_name} on TableTap",
            "html": html_content,
        })
        print(f"Successfully sent invitation email to {email}: {r}")
        return True
    except Exception as e:
        print(f"Failed to send email to {email}: {e}")
        return False
