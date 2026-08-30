"""
Django management command to seed a complete demo restaurant with menu categories,
dishes, tables, and a default owner user account.

Usage:
    python manage.py seed_demo
"""
from django.core.management.base import BaseCommand
from django.db import connection
from django.utils import timezone
from django_tenants.utils import schema_context


class Command(BaseCommand):
    help = "Seed demo restaurant data, user account, menu items, and tables"

    def handle(self, *args, **options):
        from tenants.models import Tenant, Domain
        from django.contrib.auth import get_user_model

        User = get_user_model()
        connection.set_schema_to_public()

        # ── 1. Create Default Owner User ──────────────────────────────────────
        self.stdout.write("1. Creating default owner user...")
        email = "admin@tabletap.space"
        password = "password123"

        owner, created = User.objects.get_or_create(
            email=email,
            defaults={
                "username": email,
                "name": "Demo Admin",
                "role": "owner",
                "is_staff": True,
                "is_active": True,
                "is_verified": True,
            },
        )
        if created or not owner.check_password(password):
            owner.set_password(password)
            owner.save()
            self.stdout.write(self.style.SUCCESS(f"   ✓ Owner user ready: {email} / {password}"))
        else:
            self.stdout.write(f"   ✓ Owner user already exists: {email}")

        # ── 2. Create Demo Restaurant Tenant ─────────────────────────────────
        self.stdout.write("\n2. Creating demo restaurant tenant...")
        tenant_slug = "tabletap-restaurant"
        tenant, created = Tenant.objects.get_or_create(
            slug=tenant_slug,
            defaults={
                "name": "TableTap Restaurant",
                "schema_name": "tabletap_restaurant",
                "contact_email": email,
                "address": "East Legon, Accra",
                "phone": "+233 50 123 4567",
                "currency": "GHS",
                "timezone": "UTC",
                "is_active": True,
                "owner": owner,
                "settings": {
                    "taxRate": 10,
                    "deliveryFee": 15,
                    "paymentMethods": ["cash", "momo"],
                    "momoNumber": "0241234567",
                },
            },
        )
        if created:
            self.stdout.write(self.style.SUCCESS(f"   ✓ Tenant created: {tenant.name} ({tenant.slug})"))
        else:
            self.stdout.write(f"   ✓ Tenant already exists: {tenant.name} ({tenant.slug})")

        # ── 3. Register Domain ────────────────────────────────────────────────
        Domain.objects.get_or_create(
            domain=f"{tenant_slug}.localhost",
            defaults={"tenant": tenant, "is_primary": False},
        )

        # ── 4. Seed Menu Items in Tenant Schema ──────────────────────────────
        self.stdout.write("\n3. Seeding categories and menu items...")
        with schema_context(tenant.schema_name):
            from menu.models import Category, MenuItem
            from restaurant_tables.models import Table

            # Categories
            cat_grills, _ = Category.objects.get_or_create(name="Grills & Mains", defaults={"priority": 1})
            cat_drinks, _ = Category.objects.get_or_create(name="Drinks & Beverages", defaults={"priority": 2})
            cat_sides, _ = Category.objects.get_or_create(name="Sides & Desserts", defaults={"priority": 3})

            dishes = [
                (cat_grills, "Jollof Rice with Grilled Chicken", "Smoky Ghanain Jollof served with spiced grilled chicken and fried plantains.", 45.00),
                (cat_grills, "Grilled Tilapia with Banku", "Freshly grilled whole tilapia served with spicy pepper sauce and hot Banku.", 65.00),
                (cat_grills, "Beef Suya Platter", "Tender beef skewers coated in authentic Yaji suya spice blend.", 50.00),
                (cat_drinks, "Fresh Hibiscus Sobolo", "Chilled traditional hibiscus tea with ginger and pineapple notes.", 15.00),
                (cat_drinks, "Chilled Coca Cola (330ml)", "Cold canned Coca-Cola.", 10.00),
                (cat_drinks, "Fresh Pineapple Juice", "100% natural cold pressed pineapple juice.", 20.00),
                (cat_sides, "Fried Plantain (Kelewele)", "Spiced sweet fried plantain cubes.", 15.00),
                (cat_sides, "Crispy French Fries", "Golden salted french fries served with ketchup.", 20.00),
            ]

            for cat, name, desc, price in dishes:
                item, item_created = MenuItem.objects.get_or_create(
                    category=cat,
                    name=name,
                    defaults={
                        "description": desc,
                        "price": price,
                        "isAvailable": True,
                    },
                )
                if item_created:
                    self.stdout.write(f"   ✓ Added dish: {name} - GHS {price:.2f}")

            # Tables
            for table_num in range(1, 6):
                Table.objects.get_or_create(
                    number=table_num,
                    defaults={"capacity": 4, "status": "active"},
                )


        self.stdout.write("\n" + "="*50)
        self.stdout.write(self.style.SUCCESS(" 🎉 Demo restaurant seeding complete!"))
        self.stdout.write(" Login Email:    admin@tabletap.space")
        self.stdout.write(" Login Password: password123")
        self.stdout.write(" Tenant Slug:    tabletap-restaurant")
        self.stdout.write("="*50 + "\n")
