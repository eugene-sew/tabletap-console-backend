from django.core.management.base import BaseCommand
from subscriptions.models import Plan

class Command(BaseCommand):
    help = 'Create sample subscription plans'

    def handle(self, *args, **options):
        plans_data = [
            {
                'name': 'Starter',
                'plan_type': 'basic',
                'description': 'Perfect for small restaurants just getting started',
                'billing_cycle': 'monthly',
                'price_usd': 29.99,
                'price_ghs': 180.00,
                'price_ngn': 45000.00,
                'includes_pos': True,
                'includes_menu': True,
                'includes_cms': False,
                'includes_analytics': False,
                'includes_inventory': False,
                'max_staff': 3,
                'max_tables': 5,
                'max_menu_items': 50,
                'max_locations': 1,
                'is_featured': False,
                'sort_order': 1,
            },
            {
                'name': 'Professional',
                'plan_type': 'standard',
                'description': 'Ideal for growing restaurants with multiple staff',
                'billing_cycle': 'monthly',
                'price_usd': 59.99,
                'price_ghs': 360.00,
                'price_ngn': 90000.00,
                'includes_pos': True,
                'includes_menu': True,
                'includes_cms': True,
                'includes_analytics': True,
                'includes_inventory': False,
                'max_staff': 10,
                'max_tables': 15,
                'max_menu_items': 200,
                'max_locations': 1,
                'is_featured': True,
                'sort_order': 2,
            },
            {
                'name': 'Business',
                'plan_type': 'premium',
                'description': 'Complete solution for established restaurants',
                'billing_cycle': 'monthly',
                'price_usd': 99.99,
                'price_ghs': 600.00,
                'price_ngn': 150000.00,
                'includes_pos': True,
                'includes_menu': True,
                'includes_cms': True,
                'includes_analytics': True,
                'includes_inventory': True,
                'max_staff': 25,
                'max_tables': 30,
                'max_menu_items': 500,
                'max_locations': 3,
                'is_featured': False,
                'sort_order': 3,
            },
            {
                'name': 'Enterprise',
                'plan_type': 'enterprise',
                'description': 'Custom solution for restaurant chains and franchises',
                'billing_cycle': 'monthly',
                'price_usd': 199.99,
                'price_ghs': 1200.00,
                'price_ngn': 300000.00,
                'includes_pos': True,
                'includes_menu': True,
                'includes_cms': True,
                'includes_analytics': True,
                'includes_inventory': True,
                'max_staff': 100,
                'max_tables': 100,
                'max_menu_items': 1000,
                'max_locations': 10,
                'is_featured': False,
                'sort_order': 4,
            },
        ]

        for plan_data in plans_data:
            plan, created = Plan.objects.get_or_create(
                name=plan_data['name'],
                billing_cycle=plan_data['billing_cycle'],
                defaults=plan_data
            )
            
            if created:
                self.stdout.write(
                    self.style.SUCCESS(f'Created plan: {plan.name}')
                )
            else:
                self.stdout.write(
                    self.style.WARNING(f'Plan already exists: {plan.name}')
                )

        self.stdout.write(
            self.style.SUCCESS('Successfully created sample plans!')
        )
