from django.core.management.base import BaseCommand
from subscriptions.models import Plan
from tools.models import Tool
from staff.models import Role

class Command(BaseCommand):
    help = 'Setup initial data for TableTap Console'

    def handle(self, *args, **options):
        # Create subscription plans
        plans = [
            {
                'name': 'Basic',
                'description': 'Basic plan with POS access',
                'price_ghs': 50.00,
                'price_ngn': 5000.00,
                'price_usd': 15.00,
                'includes_pos': True,
                'max_staff': 5,
                'max_tables': 10,
                'max_menu_items': 50,
            },
            {
                'name': 'Professional',
                'description': 'Professional plan with POS and Menu management',
                'price_ghs': 100.00,
                'price_ngn': 10000.00,
                'price_usd': 30.00,
                'includes_pos': True,
                'includes_menu': True,
                'max_staff': 15,
                'max_tables': 25,
                'max_menu_items': 200,
            },
            {
                'name': 'Enterprise',
                'description': 'Full suite with POS, Menu, and CMS',
                'price_ghs': 200.00,
                'price_ngn': 20000.00,
                'price_usd': 60.00,
                'includes_pos': True,
                'includes_menu': True,
                'includes_cms': True,
                'max_staff': 50,
                'max_tables': 100,
                'max_menu_items': 1000,
            }
        ]

        for plan_data in plans:
            plan, created = Plan.objects.get_or_create(
                name=plan_data['name'],
                defaults=plan_data
            )
            if created:
                self.stdout.write(f'Created plan: {plan.name}')

        # Create tools
        tools = [
            {
                'name': 'POS',
                'description': 'Point of Sale system',
                'url': 'https://pos.tabletap.com',
            },
            {
                'name': 'Menu',
                'description': 'Menu management system',
                'url': 'https://menu.tabletap.com',
            },
            {
                'name': 'CMS',
                'description': 'Content management system',
                'url': 'https://cms.tabletap.com',
            }
        ]

        for tool_data in tools:
            tool, created = Tool.objects.get_or_create(
                name=tool_data['name'],
                defaults=tool_data
            )
            if created:
                self.stdout.write(f'Created tool: {tool.name}')

        self.stdout.write(self.style.SUCCESS('Successfully setup initial data'))
