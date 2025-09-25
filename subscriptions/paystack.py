import requests
from django.conf import settings

class PaystackAPI:
    BASE_URL = 'https://api.paystack.co'
    
    def __init__(self):
        self.secret_key = settings.PAYSTACK_SECRET_KEY
        self.headers = {
            'Authorization': f'Bearer {self.secret_key}',
            'Content-Type': 'application/json'
        }
    
    def create_customer(self, email, first_name, last_name, phone=None):
        """Create a customer on Paystack"""
        url = f'{self.BASE_URL}/customer'
        data = {
            'email': email,
            'first_name': first_name,
            'last_name': last_name,
        }
        if phone:
            data['phone'] = phone
        
        response = requests.post(url, json=data, headers=self.headers)
        return response.json()
    
    def create_plan(self, name, amount, currency='NGN', interval='monthly'):
        """Create a subscription plan"""
        url = f'{self.BASE_URL}/plan'
        data = {
            'name': name,
            'amount': int(amount * 100),  # Paystack uses kobo/cents
            'currency': currency,
            'interval': interval
        }
        
        response = requests.post(url, json=data, headers=self.headers)
        return response.json()
    
    def create_subscription(self, customer_code, plan_code):
        """Create a subscription"""
        url = f'{self.BASE_URL}/subscription'
        data = {
            'customer': customer_code,
            'plan': plan_code
        }
        
        response = requests.post(url, json=data, headers=self.headers)
        return response.json()
    
    def initialize_payment(self, email, amount, currency='NGN', callback_url=None):
        """Initialize a payment"""
        url = f'{self.BASE_URL}/transaction/initialize'
        data = {
            'email': email,
            'amount': int(amount * 100),  # Convert to kobo/cents
            'currency': currency
        }
        if callback_url:
            data['callback_url'] = callback_url
        
        response = requests.post(url, json=data, headers=self.headers)
        return response.json()
    
    def verify_payment(self, reference):
        """Verify a payment"""
        url = f'{self.BASE_URL}/transaction/verify/{reference}'
        response = requests.get(url, headers=self.headers)
        return response.json()
