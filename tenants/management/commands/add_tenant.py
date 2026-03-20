from django.core.management.base import BaseCommand
from tenants.models import Tenant, Domain

class Command(BaseCommand):
    help = 'Create a new tenant and domain'

    def add_arguments(self, parser):
        parser.add_argument('--name', type=str, required=True, help='Tenant name')
        parser.add_argument('--schema', type=str, required=True, help='Schema name')
        parser.add_argument('--domain', type=str, required=True, help='Domain name')

    def handle(self, *args, **options):
        name = options['name']
        schema = options['schema']
        domain_name = options['domain']

        try:
            # Create Tenant
            tenant, created = Tenant.objects.get_or_create(
                schema_name=schema,
                defaults={
                    'name': name,
                    'slug': schema
                }
            )

            if not created:
                 self.stdout.write(self.style.WARNING(f'Tenant with schema "{schema}" already exists.'))
            else:
                self.stdout.write(self.style.SUCCESS(f'Created tenant record for "{name}".'))

            # Create Domain
            Domain.objects.get_or_create(
                domain=domain_name,
                tenant=tenant,
                defaults={'is_primary': True}
            )

            self.stdout.write(self.style.SUCCESS(f'Successfully setup tenant "{name}" with domain "{domain_name}"'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error creating tenant: {str(e)}'))
