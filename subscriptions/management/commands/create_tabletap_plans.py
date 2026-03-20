from django.core.management.base import BaseCommand
from subscriptions.models import Plan

class Command(BaseCommand):
    help = 'Create TableTap subscription plans'

    def handle(self, *args, **options):
        # Clear existing plans
        Plan.objects.all().delete()
        
        plans_data = [
            {
                'name': 'Free',
                'plan_type': 'free',
                'description': 'Get started with basic digital menu features',
                'price_usd': 0.00,
                'includes_digital_menu': True,
                'includes_pos': False,
                'includes_cms': False,
                'allows_menu_images': False,
                'max_menu_items': 10,
                'has_basic_analytics': False,
                'has_advanced_analytics': False,
                'has_multi_location': False,
                'has_custom_integrations': False,
                'support_level': 'email',
                'is_featured': False,
                'sort_order': 0,
            },
            {
                'name': 'Starter',
                'plan_type': 'starter',
                'description': 'Perfect for small restaurants getting started with digital solutions',
                'price_usd': 7.99,
                'includes_digital_menu': True,
                'includes_pos': False,
                'includes_cms': False,
                'allows_menu_images': True,
                'max_menu_items': 50,
                'has_basic_analytics': True,
                'has_advanced_analytics': False,
                'has_multi_location': False,
                'has_custom_integrations': False,
                'support_level': 'email',
                'is_featured': False,
                'sort_order': 1,
            },
            {
                'name': 'Professional',
                'plan_type': 'professional',
                'description': 'Complete solution for growing restaurants with POS system',
                'price_usd': 19.99,
                'includes_digital_menu': True,
                'includes_pos': True,
                'includes_cms': False,
                'allows_menu_images': True,
                'max_menu_items': -1,  # Unlimited
                'has_basic_analytics': True,
                'has_advanced_analytics': True,
                'has_multi_location': False,
                'has_custom_integrations': False,
                'support_level': 'priority',
                'is_featured': True,
                'sort_order': 2,
            },
            {
                'name': 'Enterprise',
                'plan_type': 'enterprise',
                'description': 'Full-featured solution for established restaurants and chains',
                'price_usd': 39.99,
                'includes_digital_menu': True,
                'includes_pos': True,
                'includes_cms': True,
                'allows_menu_images': True,
                'max_menu_items': -1,  # Unlimited
                'has_basic_analytics': True,
                'has_advanced_analytics': True,
                'has_multi_location': True,
                'has_custom_integrations': True,
                'support_level': 'phone_24_7',
                'is_featured': False,
                'sort_order': 3,
            },
        ]

        for plan_data in plans_data:
            plan = Plan.objects.create(**plan_data)
            self.stdout.write(
                self.style.SUCCESS(f'Created plan: {plan.name} - ${plan.price_usd}/month')
            )

        self.stdout.write(
            self.style.SUCCESS('Successfully created TableTap subscription plans!')
        )
