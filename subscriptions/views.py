from rest_framework import status, permissions
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet
from django.shortcuts import get_object_or_404
from django.utils import timezone
from datetime import timedelta
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi
import uuid
import requests
from django.conf import settings

from .models import Plan, Subscription, Payment
from .serializers import (
    PlanSerializer, SubscriptionSerializer, PaymentSerializer,
    CreateSubscriptionSerializer, PaystackPaymentSerializer
)
from tenants.models import Tenant

class PlanViewSet(ModelViewSet):
    """
    ViewSet for managing subscription plans.
    Only active plans are shown to customers.
    """
    queryset = Plan.objects.filter(is_active=True)
    serializer_class = PlanSerializer
    permission_classes = [permissions.AllowAny]  # Plans are public
    http_method_names = ['get']  # Read-only for customers

@swagger_auto_schema(
    method='get',
    operation_description="Get current user's subscription details",
    responses={
        200: SubscriptionSerializer,
        404: 'No subscription found'
    }
)
@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def get_user_subscription(request):
    """Get current user's subscription"""
    try:
        # Get user's tenant
        tenant = Tenant.objects.get(clerk_organization_id=request.user.clerk_user_id)
        subscription = Subscription.objects.get(tenant=tenant)
        serializer = SubscriptionSerializer(subscription)
        return Response(serializer.data)
    except (Tenant.DoesNotExist, Subscription.DoesNotExist):
        return Response({'error': 'No subscription found'}, status=404)

@swagger_auto_schema(
    method='post',
    operation_description="Create a new subscription",
    request_body=CreateSubscriptionSerializer,
    responses={
        201: SubscriptionSerializer,
        400: 'Invalid data'
    }
)
@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def create_subscription(request):
    """Create a new subscription for the user's tenant"""
    serializer = CreateSubscriptionSerializer(data=request.data)
    if serializer.is_valid():
        try:
            # Get user's tenant
            tenant = Tenant.objects.get(clerk_organization_id=request.user.clerk_user_id)
            
            # Check if tenant already has a subscription
            if hasattr(tenant, 'subscription'):
                return Response({'error': 'Tenant already has a subscription'}, status=400)
            
            plan = Plan.objects.get(id=serializer.validated_data['plan_id'])
            
            # Create subscription
            subscription = Subscription.objects.create(
                tenant=tenant,
                plan=plan,
                status='trialing',
                current_period_start=timezone.now(),
                current_period_end=timezone.now() + timedelta(days=30),
                trial_end=timezone.now() + timedelta(days=7)
            )
            
            response_serializer = SubscriptionSerializer(subscription)
            return Response(response_serializer.data, status=201)
            
        except Tenant.DoesNotExist:
            return Response({'error': 'No tenant found for user'}, status=404)
        except Plan.DoesNotExist:
            return Response({'error': 'Plan not found'}, status=404)
    
    return Response(serializer.errors, status=400)

@swagger_auto_schema(
    method='post',
    operation_description="Initialize Paystack payment for subscription",
    request_body=PaystackPaymentSerializer,
    responses={
        200: openapi.Response(
            description="Payment initialization successful",
            schema=openapi.Schema(
                type=openapi.TYPE_OBJECT,
                properties={
                    'authorization_url': openapi.Schema(type=openapi.TYPE_STRING),
                    'access_code': openapi.Schema(type=openapi.TYPE_STRING),
                    'reference': openapi.Schema(type=openapi.TYPE_STRING),
                }
            )
        )
    }
)
@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def initialize_payment(request):
    """Initialize Paystack payment for subscription"""
    serializer = PaystackPaymentSerializer(data=request.data)
    if serializer.is_valid():
        try:
            subscription = Subscription.objects.get(id=serializer.validated_data['subscription_id'])
            currency = serializer.validated_data['currency']
            
            # Verify user owns this subscription
            if subscription.tenant.clerk_organization_id != request.user.clerk_user_id:
                return Response({'error': 'Unauthorized'}, status=403)
            
            amount = subscription.plan.get_price_in_currency(currency)
            
            # Generate unique reference
            reference = f"ttc_{uuid.uuid4().hex[:12]}"
            
            # Create payment record
            payment = Payment.objects.create(
                subscription=subscription,
                amount=amount,
                currency=currency,
                paystack_reference=reference,
                status='pending'
            )
            
            # Initialize Paystack payment
            paystack_data = {
                'email': request.user.email,
                'amount': int(amount * 100),  # Paystack expects kobo/cents
                'currency': currency,
                'reference': reference,
                'callback_url': serializer.validated_data.get('callback_url', ''),
                'metadata': {
                    'subscription_id': subscription.id,
                    'tenant_name': subscription.tenant.name,
                    'plan_name': subscription.plan.name
                }
            }
            
            headers = {
                'Authorization': f'Bearer {settings.PAYSTACK_SECRET_KEY}',
                'Content-Type': 'application/json'
            }
            
            response = requests.post(
                'https://api.paystack.co/transaction/initialize',
                json=paystack_data,
                headers=headers
            )
            
            if response.status_code == 200:
                paystack_response = response.json()
                if paystack_response['status']:
                    # Update payment with access code
                    payment.paystack_access_code = paystack_response['data']['access_code']
                    payment.save()
                    
                    return Response({
                        'authorization_url': paystack_response['data']['authorization_url'],
                        'access_code': paystack_response['data']['access_code'],
                        'reference': reference,
                        'amount': amount,
                        'currency': currency
                    })
            
            return Response({'error': 'Payment initialization failed'}, status=400)
            
        except Subscription.DoesNotExist:
            return Response({'error': 'Subscription not found'}, status=404)
    
    return Response(serializer.errors, status=400)

@swagger_auto_schema(
    method='post',
    operation_description="Paystack webhook for payment verification",
    request_body=openapi.Schema(type=openapi.TYPE_OBJECT),
    responses={200: 'Webhook processed'}
)
@api_view(['POST'])
@permission_classes([permissions.AllowAny])
def paystack_webhook(request):
    """Handle Paystack webhooks"""
    event = request.data.get('event')
    data = request.data.get('data', {})
    
    if event == 'charge.success':
        reference = data.get('reference')
        
        try:
            payment = Payment.objects.get(paystack_reference=reference)
            
            # Update payment status
            payment.status = 'success'
            payment.paid_at = timezone.now()
            payment.payment_method = data.get('channel', '')
            payment.save()
            
            # Update subscription status
            subscription = payment.subscription
            subscription.status = 'active'
            subscription.current_period_start = timezone.now()
            
            # Set next billing period based on plan
            if subscription.plan.billing_cycle == 'yearly':
                subscription.current_period_end = timezone.now() + timedelta(days=365)
            else:
                subscription.current_period_end = timezone.now() + timedelta(days=30)
            
            subscription.save()
            
            return Response({'status': 'success'})
            
        except Payment.DoesNotExist:
            return Response({'error': 'Payment not found'}, status=404)
    
    return Response({'status': 'processed'})

@swagger_auto_schema(
    method='get',
    operation_description="Get subscription payment history",
    responses={200: PaymentSerializer(many=True)}
)
@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def get_payment_history(request):
    """Get payment history for user's subscription"""
    try:
        tenant = Tenant.objects.get(clerk_organization_id=request.user.clerk_user_id)
        subscription = Subscription.objects.get(tenant=tenant)
        payments = Payment.objects.filter(subscription=subscription).order_by('-created_at')
        serializer = PaymentSerializer(payments, many=True)
        return Response(serializer.data)
    except (Tenant.DoesNotExist, Subscription.DoesNotExist):
        return Response({'error': 'No subscription found'}, status=404)
