from django.core.management.base import BaseCommand
from tenants.models import Tenant, Domain

class Command(BaseCommand):
    help = 'Create a domain for the public tenant'

    def add_arguments(self, parser):
        parser.add_argument('--domain', type=str, required=True, help='Domain name to add to public tenant')

    def handle(self, *args, **options):
        domain_name = options['domain']

        try:
            # Get or create public tenant (schema_name='public')
            public_tenant, created = Tenant.objects.get_or_create(
                schema_name='public',
                defaults={
                    'name': 'TableTap Public',
                    'slug': 'public'
                }
            )
            
            if created:
                self.stdout.write(self.style.SUCCESS('Created public tenant record.'))

            # Create Domain
            domain, d_created = Domain.objects.get_or_create(
                domain=domain_name,
                tenant=public_tenant,
                defaults={'is_primary': True}
            )

            if d_created:
                self.stdout.write(self.style.SUCCESS(f'Successfully added domain "{domain_name}" to public tenant'))
            else:
                self.stdout.write(self.style.WARNING(f'Domain "{domain_name}" already exists for public tenant'))

        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error: {str(e)}'))
