from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from django.contrib.auth import get_user_model
from django.db import connection
from django_tenants.utils import tenant_context
from tenants.models import Tenant
from django.utils import timezone
from datetime import timedelta

User = get_user_model()


def superadmin_check(request):
    return request.user.is_authenticated and request.user.is_staff


# ── Overview / Dashboard ─────────────────────────────────────────────────────

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def overview(request):
    if not superadmin_check(request):
        return Response({'error': 'Super admin access required'}, status=403)

    connection.set_schema_to_public()

    tenants = Tenant.objects.exclude(schema_name='public')
    users   = User.objects.all()

    tenant_details = []
    for t in tenants:
        with tenant_context(t):
            try:
                from staff.models import StaffMember
                staff_count = StaffMember.objects.count()
            except Exception:
                staff_count = 0
        tenant_details.append({
            'id':           t.id,
            'name':         t.name,
            'slug':         t.slug or t.schema_name,
            'schema_name':  t.schema_name,
            'is_active':    t.is_active,
            'created_on':   t.created_on.isoformat() if hasattr(t, 'created_on') and t.created_on else None,
            'staff_count':  staff_count,
        })

    recent_users = users.order_by('-date_joined')[:5].values(
        'id', 'email', 'first_name', 'last_name', 'role', 'is_active', 'date_joined'
    )

    return Response({
        'stats': {
            'total_tenants':  tenants.count(),
            'active_tenants': tenants.filter(is_active=True).count(),
            'total_users':    users.count(),
            'active_users':   users.filter(is_active=True).count(),
            'staff_users':    users.filter(role='staff').count(),
            'owner_users':    users.filter(role='owner').count(),
        },
        'tenants':      tenant_details,
        'recent_users': list(recent_users),
    })


# ── Tenants ──────────────────────────────────────────────────────────────────

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def tenant_list(request):
    if not superadmin_check(request):
        return Response({'error': 'Super admin access required'}, status=403)

    connection.set_schema_to_public()
    tenants = Tenant.objects.exclude(schema_name='public').order_by('-id')

    result = []
    for t in tenants:
        owner = User.objects.filter(clerk_user_id=t.clerk_organization_id).first()
        with tenant_context(t):
            try:
                from staff.models import StaffMember
                staff_count = StaffMember.objects.count()
                active_staff = StaffMember.objects.filter(is_active=True).count()
            except Exception:
                staff_count = active_staff = 0
        result.append({
            'id':            t.id,
            'name':          t.name,
            'slug':          t.slug or t.schema_name,
            'schema_name':   t.schema_name,
            'is_active':     t.is_active,
            'created_on':    t.created_on.isoformat() if hasattr(t, 'created_on') and t.created_on else None,
            'staff_count':   staff_count,
            'active_staff':  active_staff,
            'owner': {
                'id':         owner.id if owner else None,
                'email':      owner.email if owner else None,
                'first_name': owner.first_name if owner else None,
                'last_name':  owner.last_name if owner else None,
            } if owner else None,
        })

    return Response(result)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def tenant_detail(request, tenant_id):
    if not superadmin_check(request):
        return Response({'error': 'Super admin access required'}, status=403)

    connection.set_schema_to_public()
    try:
        t = Tenant.objects.get(id=tenant_id)
    except Tenant.DoesNotExist:
        return Response({'error': 'Tenant not found'}, status=404)

    owner = User.objects.filter(clerk_user_id=t.clerk_organization_id).first()
    members = []
    with tenant_context(t):
        try:
            from staff.models import StaffMember
            for sm in StaffMember.objects.select_related('user', 'role').all():
                members.append({
                    'id':         sm.id,
                    'is_active':  sm.is_active,
                    'hired_date': sm.hired_date.isoformat() if sm.hired_date else None,
                    'role':       sm.role.name if sm.role else None,
                    'user': {
                        'id':         sm.user.id,
                        'email':      sm.user.email,
                        'first_name': sm.user.first_name,
                        'last_name':  sm.user.last_name,
                    },
                })
        except Exception:
            pass

    return Response({
        'id':           t.id,
        'name':         t.name,
        'slug':         t.slug or t.schema_name,
        'schema_name':  t.schema_name,
        'is_active':    t.is_active,
        'created_on':   t.created_on.isoformat() if hasattr(t, 'created_on') and t.created_on else None,
        'owner':        {
            'id': owner.id, 'email': owner.email,
            'first_name': owner.first_name, 'last_name': owner.last_name,
        } if owner else None,
        'members': members,
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def tenant_toggle(request, tenant_id):
    if not superadmin_check(request):
        return Response({'error': 'Super admin access required'}, status=403)

    connection.set_schema_to_public()
    try:
        t = Tenant.objects.get(id=tenant_id)
    except Tenant.DoesNotExist:
        return Response({'error': 'Tenant not found'}, status=404)

    t.is_active = not t.is_active
    t.save(update_fields=['is_active'])
    return Response({'id': t.id, 'is_active': t.is_active})


# ── Users ────────────────────────────────────────────────────────────────────

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def user_list(request):
    if not superadmin_check(request):
        return Response({'error': 'Super admin access required'}, status=403)

    connection.set_schema_to_public()

    search = request.query_params.get('search', '').strip()
    role_filter = request.query_params.get('role', '')

    qs = User.objects.all().order_by('-date_joined')
    if search:
        from django.db.models import Q
        qs = qs.filter(
            Q(email__icontains=search) |
            Q(first_name__icontains=search) |
            Q(last_name__icontains=search)
        )
    if role_filter:
        qs = qs.filter(role=role_filter)

    result = []
    for u in qs[:200]:
        tenant_name = None
        t = Tenant.objects.filter(clerk_organization_id=u.clerk_user_id).first()
        if t:
            tenant_name = t.name
        else:
            for candidate in Tenant.objects.exclude(schema_name='public'):
                with tenant_context(candidate):
                    try:
                        from staff.models import StaffMember
                        if StaffMember.objects.filter(user=u).exists():
                            tenant_name = candidate.name
                            break
                    except Exception:
                        pass

        result.append({
            'id':          u.id,
            'email':       u.email,
            'first_name':  u.first_name,
            'last_name':   u.last_name,
            'username':    u.username,
            'role':        u.role,
            'is_active':   u.is_active,
            'is_staff':    u.is_staff,
            'date_joined': u.date_joined.isoformat() if u.date_joined else None,
            'tenant_name': tenant_name,
        })

    return Response(result)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def user_toggle_active(request, user_id):
    if not superadmin_check(request):
        return Response({'error': 'Super admin access required'}, status=403)

    connection.set_schema_to_public()
    try:
        u = User.objects.get(id=user_id)
    except User.DoesNotExist:
        return Response({'error': 'User not found'}, status=404)

    u.is_active = not u.is_active
    u.save(update_fields=['is_active'])
    return Response({'id': u.id, 'is_active': u.is_active})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def user_toggle_staff(request, user_id):
    if not superadmin_check(request):
        return Response({'error': 'Super admin access required'}, status=403)

    connection.set_schema_to_public()
    try:
        u = User.objects.get(id=user_id)
    except User.DoesNotExist:
        return Response({'error': 'User not found'}, status=404)

    u.is_staff = not u.is_staff
    u.save(update_fields=['is_staff'])
    return Response({'id': u.id, 'is_staff': u.is_staff})
