from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from .models import Role, StaffMember
from .serializers import RoleSerializer, StaffMemberSerializer


class RoleViewSet(viewsets.ModelViewSet):
    queryset = Role.objects.all()
    serializer_class = RoleSerializer

    def get_queryset(self):
        return Role.objects.all()

    def perform_create(self, serializer):
        serializer.save(tenant=self.request.tenant)


class StaffMemberViewSet(viewsets.ModelViewSet):
    queryset = StaffMember.objects.all()
    serializer_class = StaffMemberSerializer

    def get_queryset(self):
        return StaffMember.objects.select_related('user', 'role')

    @action(detail=False, methods=['GET'])
    def me(self, request):
        """Get current staff member profile."""
        try:
            staff = StaffMember.objects.filter(
                user=request.user, tenant=request.tenant
            ).first()
        except Exception:
            return Response(
                {'error': 'No staff profile found for current user'}, status=404
            )

        if not staff:
            is_tenant_owner = (
                hasattr(request.tenant, 'clerk_organization_id')
                and request.tenant.clerk_organization_id == request.user.clerk_user_id
            )
            if getattr(request.user, 'role', None) == 'owner' and is_tenant_owner:
                try:
                    owner_role, _ = Role.objects.get_or_create(
                        tenant=request.tenant,
                        name='Owner',
                        defaults={
                            'description': 'Full administrative access',
                            'permissions': {'*': True},
                        }
                    )
                    staff = StaffMember.objects.create(
                        user=request.user,
                        tenant=request.tenant,
                        role=owner_role,
                        is_active=True,
                    )
                except Exception:
                    pass

        if not staff:
            return Response(
                {'error': 'No staff profile found for current user'}, status=404
            )

        serializer = self.get_serializer(staff)
        print(f"[DEBUG] Returning staff profile: {serializer.data}")
        return Response(serializer.data)

    def create(self, request, *args, **kwargs):
        """
        Invite a staff member.
        - If the user doesn't exist yet, create a placeholder and send an invitation email.
        - If the user already exists (e.g., re-invite or cross-tenant), send the email and
          link them.
        """
        email = request.data.get('email', '').strip().lower()
        first_name = request.data.get('first_name', '')
        last_name = request.data.get('last_name', '')
        role_id = request.data.get('role_id')

        role_name = 'Staff Member'
        if role_id:
            try:
                role_obj = Role.objects.get(id=role_id)
                role_name = role_obj.name
            except Role.DoesNotExist:
                pass

        should_send_email = False

        if email:
            from django.contrib.auth import get_user_model
            User = get_user_model()

            try:
                user = User.objects.get(email=email)
                if first_name and not user.first_name:
                    user.first_name = first_name
                    user.last_name = last_name
                    user.save(update_fields=['first_name', 'last_name'])
                request.data['user_id'] = user.id
                # Re-send email so existing users get the role-specific invite
                should_send_email = True

            except User.DoesNotExist:
                user = User.objects.create(
                    username=email,
                    email=email,
                    first_name=first_name,
                    last_name=last_name,
                    role='staff',
                    is_active=False,
                )
                request.data['user_id'] = user.id
                should_send_email = True

            if should_send_email:
                from utils.email import send_staff_invitation_email
                from django.conf import settings as django_settings
                from django.core import signing

                frontend_url = getattr(django_settings, 'FRONTEND_URL', None)
                invite_token = signing.dumps(
                    {'user_id': user.id},
                    salt='staff_invitation',
                )
                send_staff_invitation_email(
                    email=email,
                    first_name=first_name,
                    role_name=role_name,
                    tenant_name=request.tenant.name,
                    frontend_url=frontend_url,
                    invite_token=invite_token,
                )
                try:
                    from analytics.audit import log_action
                    log_action(
                        request,
                        action='staff.invited',
                        entity_type='staff',
                        entity_id=user.id,
                        entity_label=f"{first_name} {last_name}".strip() or email,
                        metadata={'email': email, 'role': role_name},
                    )
                except Exception:
                    pass

        return super().create(request, *args, **kwargs)

    def perform_create(self, serializer):
        serializer.save(tenant=self.request.tenant)

    def perform_destroy(self, instance):
        try:
            from analytics.audit import log_action
            log_action(
                self.request,
                action='staff.deleted',
                entity_type='staff',
                entity_id=instance.user.id,
                entity_label=f"{instance.user.get_full_name() or instance.user.email}",
                metadata={'email': instance.user.email, 'role': instance.role.name if instance.role else ''},
            )
        except Exception:
            pass
        instance.delete()

    def perform_update(self, serializer):
        old_role = serializer.instance.role
        instance = serializer.save()
        try:
            if old_role != instance.role:
                from analytics.audit import log_action
                log_action(
                    self.request,
                    action='staff.role_changed',
                    entity_type='staff',
                    entity_id=instance.user.id,
                    entity_label=f"{instance.user.get_full_name() or instance.user.email}",
                    metadata={
                        'email': instance.user.email,
                        'from_role': old_role.name if old_role else '',
                        'to_role': instance.role.name if instance.role else '',
                    },
                )
        except Exception:
            pass

    @action(detail=True, methods=['post'])
    def deactivate(self, request, pk=None):
        """Deactivate staff member."""
        staff = self.get_object()
        staff.is_active = False
        staff.save()
        try:
            from analytics.audit import log_action
            log_action(
                request,
                action='staff.deactivated',
                entity_type='staff',
                entity_id=staff.user.id,
                entity_label=f"{staff.user.get_full_name() or staff.user.email}",
                metadata={'email': staff.user.email, 'role': staff.role.name if staff.role else ''},
            )
        except Exception:
            pass
        return Response({'status': 'staff member deactivated'})

    @action(detail=True, methods=['post'])
    def activate(self, request, pk=None):
        """Activate staff member."""
        staff = self.get_object()
        staff.is_active = True
        staff.save()
        try:
            from analytics.audit import log_action
            log_action(
                request,
                action='staff.activated',
                entity_type='staff',
                entity_id=staff.user.id,
                entity_label=f"{staff.user.get_full_name() or staff.user.email}",
                metadata={'email': staff.user.email, 'role': staff.role.name if staff.role else ''},
            )
        except Exception:
            pass
        return Response({'status': 'staff member activated'})
