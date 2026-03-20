"""
seed_local – one-time setup for a fresh local database.

Creates:
  • The public-schema Tenant row (required by django-tenants middleware)
  • Domain entries for localhost and 127.0.0.1
  • Optionally a first super-admin user

Safe to run multiple times (all operations are get_or_create).
"""

from django.core.management.base import BaseCommand
from django.db import connection


class Command(BaseCommand):
    help = "Seed the local database with the public tenant and localhost domains"

    def add_arguments(self, parser):
        parser.add_argument(
            "--admin-email",
            type=str,
            default="",
            help="Email of the first super-admin user to create (optional)",
        )

    def handle(self, *args, **options):
        from tenants.models import Tenant, Domain

        connection.set_schema_to_public()

        # ── 1. Public tenant ──────────────────────────────────────────────
        self.stdout.write("  Setting up public tenant…")
        public_tenant, created = Tenant.objects.get_or_create(
            schema_name="public",
            defaults={
                "name": "TableTap Platform",
                "slug": "public",
                "is_active": True,
            },
        )
        if created:
            self.stdout.write(self.style.SUCCESS("    ✓ Public tenant created"))
        else:
            self.stdout.write("    ✓ Public tenant already exists")

        # ── 2. Localhost domains ──────────────────────────────────────────
        self.stdout.write("  Registering local domains…")
        local_domains = [
            ("localhost",  True),
            ("127.0.0.1",  False),
        ]
        for domain_name, is_primary in local_domains:
            _, created = Domain.objects.get_or_create(
                domain=domain_name,
                defaults={"tenant": public_tenant, "is_primary": is_primary},
            )
            if created:
                self.stdout.write(
                    self.style.SUCCESS(f"    ✓ Domain '{domain_name}' created")
                )
            else:
                self.stdout.write(f"    ✓ Domain '{domain_name}' already exists")

        # ── 3. Optional super-admin user ──────────────────────────────────
        admin_email = options.get("admin_email", "").strip()
        if admin_email:
            from django.contrib.auth import get_user_model
            User = get_user_model()

            user, created = User.objects.get_or_create(
                email=admin_email,
                defaults={
                    "username": admin_email,
                    "is_staff": True,
                    "is_active": True,
                    "role": "owner",
                },
            )
            if not created and not user.is_staff:
                user.is_staff = True
                user.save(update_fields=["is_staff"])

            if created:
                self.stdout.write(
                    self.style.SUCCESS(f"    ✓ Super-admin user '{admin_email}' created")
                )
            else:
                self.stdout.write(
                    f"    ✓ User '{admin_email}' already exists (is_staff={user.is_staff})"
                )

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS("  Local seed complete."))
        self.stdout.write(
            "  The backend can now resolve requests from localhost.\n"
        )
