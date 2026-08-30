from django.db import models
from django.utils import timezone
import secrets


class TenantWhatsAppAccount(models.Model):
    """
    Shared-schema model mapping a tenant to their WhatsApp Business credentials.
    One record per restaurant that has opted in to the WhatsApp bot.
    """
    tenant = models.OneToOneField(
        'tenants.Tenant',
        on_delete=models.CASCADE,
        related_name='whatsapp_account',
    )

    # Meta / WhatsApp Cloud API credentials (per-tenant WABA)
    waba_id = models.CharField(max_length=200, blank=True, help_text='WhatsApp Business Account ID')
    phone_number_id = models.CharField(max_length=200, help_text='Meta Phone Number ID')
    phone_number = models.CharField(max_length=30, blank=True, help_text='Displayed phone number')
    access_token = models.TextField(help_text='Meta Cloud API access token (store encrypted in prod)')

    # Bot configuration
    is_active = models.BooleanField(default=True, help_text='Toggle bot on/off without disconnecting')
    bot_display_name = models.CharField(max_length=100, blank=True, help_text='Name the bot introduces itself as')
    greeting_message = models.TextField(
        blank=True,
        default='',
        help_text='Custom greeting sent on first contact',
    )

    # Owner Copilot & Proactive Alerts
    owner_phone_number = models.CharField(
        max_length=30,
        blank=True,
        default='',
        help_text="Owner's personal WhatsApp phone number for bot copilot commands and alerts",
    )
    enable_delayed_order_alerts = models.BooleanField(
        default=True,
        help_text='Proactively alert owner on WhatsApp if an order is in pending/preparing for > 30 minutes',
    )
    enable_daily_reports = models.BooleanField(
        default=True,
        help_text='Send daily evening closing revenue reports to owner on WhatsApp',
    )

    # Metadata
    connected_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'whatsapp_bot'
        verbose_name = 'Tenant WhatsApp Account'
        verbose_name_plural = 'Tenant WhatsApp Accounts'

    def __str__(self):
        return f'{self.tenant.name} → {self.phone_number or self.phone_number_id}'


class BotOwnerSession(models.Model):
    """
    Persistent record of an authenticated owner/staff bot session.
    The JWT token is short-lived; this record tracks which phone number
    is allowed to use owner commands against which tenant.
    """
    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.CASCADE,
        related_name='bot_owner_sessions',
    )
    wa_id = models.CharField(max_length=30, help_text='Owner WhatsApp phone number (wa_id)')
    staff_user_id = models.IntegerField(null=True, blank=True)
    jwt_token = models.TextField(blank=True)
    magic_token = models.CharField(max_length=64, blank=True, help_text='One-time login token')
    magic_token_expires = models.DateTimeField(null=True, blank=True)
    is_authenticated = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    last_seen = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'whatsapp_bot'
        unique_together = ('tenant', 'wa_id')
        verbose_name = 'Bot Owner Session'

    def generate_magic_token(self):
        self.magic_token = secrets.token_urlsafe(32)
        self.magic_token_expires = timezone.now() + timezone.timedelta(minutes=15)
        self.is_authenticated = False
        self.save(update_fields=['magic_token', 'magic_token_expires', 'is_authenticated'])
        return self.magic_token

    def __str__(self):
        return f'{self.tenant.name} owner session ({self.wa_id})'
