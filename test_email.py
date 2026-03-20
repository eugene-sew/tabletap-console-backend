from utils.email import send_staff_invitation_email
import os

print("RESEND_API_KEY:", os.getenv('RESEND_API_KEY')[:5] if os.getenv('RESEND_API_KEY') else 'None')

success = send_staff_invitation_email(
    email='eugenesew4+test2@gmail.com',  # Using a +alias
    first_name='Developer',
    role_name='Manager',
    tenant_name='TableTap'
)
print("Email send success:", success)
