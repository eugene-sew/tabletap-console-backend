from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from .models import Role, StaffMember
from .serializers import RoleSerializer, StaffMemberSerializer

class RoleViewSet(viewsets.ModelViewSet):
    queryset = Role.objects.all()
    serializer_class = RoleSerializer

class StaffMemberViewSet(viewsets.ModelViewSet):
    queryset = StaffMember.objects.all()
    serializer_class = StaffMemberSerializer
    
    def get_queryset(self):
        return StaffMember.objects.select_related('user', 'role')
    
    @action(detail=True, methods=['post'])
    def deactivate(self, request, pk=None):
        """Deactivate staff member"""
        staff = self.get_object()
        staff.is_active = False
        staff.save()
        return Response({'status': 'staff member deactivated'})
    
    @action(detail=True, methods=['post'])
    def activate(self, request, pk=None):
        """Activate staff member"""
        staff = self.get_object()
        staff.is_active = True
        staff.save()
        return Response({'status': 'staff member activated'})
