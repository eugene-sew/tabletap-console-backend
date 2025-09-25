from rest_framework import viewsets, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from .models import Plan, Subscription, Payment
from .serializers import PlanSerializer, SubscriptionSerializer, PaymentSerializer
from .paystack import PaystackAPI
from tenants.models import Tenant

class PlanViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Plan.objects.filter(is_active=True)
    serializer_class = PlanSerializer

class SubscriptionViewSet(viewsets.ModelViewSet):
    queryset = Subscription.objects.all()
    serializer_class = SubscriptionSerializer
    
    def get_queryset(self):
        return Subscription.objects.select_related('tenant', 'plan')

@api_view(['POST'])
def subscribe_to_plan(request):
    """Subscribe tenant to a plan"""
    tenant_id = request.data.get('tenant_id')
    plan_id = request.data.get('plan_id')
    
    tenant = get_object_or_404(Tenant, id=tenant_id)
    plan = get_object_or_404(Plan, id=plan_id)
    
    # Initialize Paystack payment
    paystack = PaystackAPI()
    
    # Create or get customer
    customer_response = paystack.create_customer(
        email=tenant.contact_email,
        first_name=tenant.name.split()[0] if tenant.name else 'Customer',
        last_name=' '.join(tenant.name.split()[1:]) if len(tenant.name.split()) > 1 else '',
        phone=tenant.contact_phone
    )
    
    if not customer_response.get('status'):
        return Response({'error': 'Failed to create customer'}, status=400)
    
    customer_code = customer_response['data']['customer_code']
    
    # Initialize payment
    amount = plan.get_price(tenant.currency)
    payment_response = paystack.initialize_payment(
        email=tenant.contact_email,
        amount=amount,
        currency=tenant.currency
    )
    
    if not payment_response.get('status'):
        return Response({'error': 'Failed to initialize payment'}, status=400)
    
    # Create payment record
    payment = Payment.objects.create(
        subscription_id=None,  # Will be set after subscription creation
        amount=amount,
        currency=tenant.currency,
        paystack_reference=payment_response['data']['reference']
    )
    
    return Response({
        'payment_url': payment_response['data']['authorization_url'],
        'reference': payment_response['data']['reference']
    })

@api_view(['POST'])
@permission_classes([AllowAny])
def paystack_webhook(request):
    """Handle Paystack webhooks"""
    event = request.data.get('event')
    data = request.data.get('data', {})
    
    if event == 'charge.success':
        reference = data.get('reference')
        
        try:
            payment = Payment.objects.get(paystack_reference=reference)
            payment.status = 'success'
            payment.save()
            
            # Update tenant subscription status
            if payment.subscription:
                subscription = payment.subscription
                subscription.status = 'active'
                subscription.save()
                
                tenant = subscription.tenant
                tenant.subscription_status = 'active'
                tenant.save()
            
        except Payment.DoesNotExist:
            pass
    
    return Response({'status': 'processed'})
