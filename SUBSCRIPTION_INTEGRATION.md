# TableTap Subscription System Integration

## Backend Setup Complete ✅

### Admin Management
- **Django Admin**: Manage plans at `/admin/subscriptions/plan/`
- **Exchange Rates**: Configure at `/admin/subscriptions/exchangeratesettings/`
- **Sample Plans**: Run `python manage.py create_tabletap_plans`
- **USD Base Pricing**: All prices set in USD, auto-convert to GHS/NGN

### TableTap Product Plans

#### **Free - $0/month**
- ✅ Digital Menu (Up to 10 menu items)
- ❌ No menu images
- ❌ No analytics
- ✅ Email support

#### **Starter - $7.99/month**
- ✅ Digital Menu (Up to 50 menu items)
- ✅ Menu images allowed
- ✅ Basic analytics
- ✅ Email support

#### **Professional - $19.99/month** (Featured)
- ✅ All Starter features
- ✅ POS System
- ✅ Unlimited menu items
- ✅ Advanced analytics
- ✅ Priority support

#### **Enterprise - $39.99/month**
- ✅ All Professional features
- ✅ Content Management System
- ✅ Multi-location support
- ✅ Custom integrations
- ✅ 24/7 phone support

### API Endpoints

#### Get Available Plans
```http
GET /api/subscriptions/plans/
```
**Response:**
```json
[
  {
    "id": 3,
    "name": "Professional",
    "plan_type": "professional",
    "description": "Complete solution for growing restaurants with POS system",
    "price_usd": 19.99,
    "price_ghs": 253.47,
    "price_ngn": 29698.50,
    "includes_digital_menu": true,
    "includes_pos": true,
    "includes_cms": false,
    "allows_menu_images": true,
    "max_menu_items": -1,
    "has_basic_analytics": true,
    "has_advanced_analytics": true,
    "has_multi_location": false,
    "has_custom_integrations": false,
    "support_level": "priority",
    "is_featured": true,
    "features_list": [
      "Digital Menu (Unlimited items)",
      "POS System", 
      "Basic Analytics",
      "Advanced Analytics",
      "Priority Support"
    ]
  }
]
```

#### Get User's Current Subscription
```http
GET /api/subscriptions/subscription/
Authorization: Bearer <token>
```

#### Create New Subscription
```http
POST /api/subscriptions/subscription/create/
Authorization: Bearer <token>
Content-Type: application/json

{
  "plan_id": 2,
  "currency": "USD"
}
```

#### Initialize Payment
```http
POST /api/subscriptions/payment/initialize/
Authorization: Bearer <token>
Content-Type: application/json

{
  "subscription_id": 1,
  "currency": "USD",
  "callback_url": "https://yourapp.com/payment/success"
}
```

**Response:**
```json
{
  "authorization_url": "https://checkout.paystack.com/...",
  "access_code": "abc123",
  "reference": "ttc_xyz789",
  "amount": 19.99,
  "currency": "USD"
}
```

## Frontend Integration

### 1. Plans Display Component
```jsx
import { useState, useEffect } from 'react';
import { useApiClient } from '../utils/api';

export const PricingPlans = () => {
  const [plans, setPlans] = useState([]);
  const [loading, setLoading] = useState(true);
  const [currency, setCurrency] = useState('USD'); // User's preferred currency
  const { apiCall } = useApiClient();

  useEffect(() => {
    const fetchPlans = async () => {
      try {
        const response = await apiCall('/api/subscriptions/plans/');
        setPlans(response);
      } catch (error) {
        console.error('Failed to fetch plans:', error);
      } finally {
        setLoading(false);
      }
    };

    fetchPlans();
  }, []);

  const formatPrice = (plan) => {
    const prices = {
      USD: `$${plan.price_usd}`,
      GHS: `₵${plan.price_ghs}`,
      NGN: `₦${plan.price_ngn}`
    };
    return prices[currency] || `$${plan.price_usd}`;
  };

  const handleSelectPlan = async (planId) => {
    try {
      // Create subscription
      const subscription = await apiCall('/api/subscriptions/subscription/create/', {
        method: 'POST',
        body: JSON.stringify({
          plan_id: planId,
          currency: currency
        })
      });

      // Initialize payment
      const payment = await apiCall('/api/subscriptions/payment/initialize/', {
        method: 'POST',
        body: JSON.stringify({
          subscription_id: subscription.id,
          currency: currency,
          callback_url: `${window.location.origin}/payment/success`
        })
      });

      // Redirect to Paystack
      window.location.href = payment.authorization_url;
    } catch (error) {
      console.error('Payment initialization failed:', error);
    }
  };

  if (loading) return <div>Loading plans...</div>;

  return (
    <div className="pricing-plans">
      {/* Currency Selector */}
      <div className="currency-selector">
        <select value={currency} onChange={(e) => setCurrency(e.target.value)}>
          <option value="USD">USD ($)</option>
          <option value="GHS">GHS (₵)</option>
          <option value="NGN">NGN (₦)</option>
        </select>
      </div>

      {plans.map(plan => (
        <div key={plan.id} className={`plan-card ${plan.is_featured ? 'featured' : ''}`}>
          <h3>{plan.name}</h3>
          <p>{plan.description}</p>
          <div className="price">
            {formatPrice(plan)}/month
          </div>
          
          <ul className="features">
            {plan.features_list.map(feature => (
              <li key={feature}>{feature}</li>
            ))}
          </ul>
          
          <div className="limits">
            {plan.max_menu_items === -1 ? (
              <p>Unlimited menu items</p>
            ) : (
              <p>Up to {plan.max_menu_items} menu items</p>
            )}
            {plan.allows_menu_images && <p>Menu images included</p>}
          </div>
          
          <button 
            onClick={() => handleSelectPlan(plan.id)}
            className="select-plan-btn"
            disabled={plan.price_usd === 0} // Free plan
          >
            {plan.price_usd === 0 ? 'Get Started Free' : `Choose ${plan.name}`}
          </button>
        </div>
      ))}
    </div>
  );
};
```

### 2. Current Subscription Component
```jsx
export const CurrentSubscription = () => {
  const [subscription, setSubscription] = useState(null);
  const { apiCall } = useApiClient();

  useEffect(() => {
    const fetchSubscription = async () => {
      try {
        const response = await apiCall('/api/subscriptions/subscription/');
        setSubscription(response);
      } catch (error) {
        console.error('No subscription found:', error);
      }
    };

    fetchSubscription();
  }, []);

  if (!subscription) {
    return <div>No active subscription</div>;
  }

  return (
    <div className="current-subscription">
      <h3>Current Plan: {subscription.plan.name}</h3>
      <p>Status: <span className={`status ${subscription.status}`}>{subscription.status}</span></p>
      <p>Price: ${subscription.plan.price_usd}/month</p>
      <p>Renews in: {subscription.days_until_renewal} days</p>
      
      <div className="plan-features">
        <h4>Your Features:</h4>
        <ul>
          {subscription.plan.features_list.map(feature => (
            <li key={feature}>✅ {feature}</li>
          ))}
        </ul>
      </div>

      <div className="plan-limits">
        <h4>Usage Limits:</h4>
        <p>Menu Items: {subscription.plan.max_menu_items === -1 ? 'Unlimited' : subscription.plan.max_menu_items}</p>
        <p>Menu Images: {subscription.plan.allows_menu_images ? 'Allowed' : 'Not allowed'}</p>
      </div>
    </div>
  );
};
```

## Deployment Steps

1. **Create and run migrations:**
```bash
python manage.py makemigrations subscriptions
python manage.py migrate
```

2. **Create TableTap plans:**
```bash
python manage.py create_tabletap_plans
```

3. **Set environment variables:**
```bash
PAYSTACK_PUBLIC_KEY=pk_test_...
PAYSTACK_SECRET_KEY=sk_test_...
```

4. **Configure Paystack webhook:**
- URL: `https://ttc.onehiveafrica.com/api/subscriptions/webhook/paystack/`
- Events: `charge.success`

## Admin Usage

### Plan Management
1. **Login to Django Admin:** `/admin/`
2. **Manage Plans:** `/admin/subscriptions/plan/`
   - Edit USD prices (auto-converts to other currencies)
   - Toggle features (POS, Menu, CMS, etc.)
   - Set limits (menu items, images, etc.)
   - Control featured status

### Exchange Rate Management
3. **Exchange Rates:** `/admin/subscriptions/exchangeratesettings/`
   - Toggle live API rates on/off
   - Set fallback USD→GHS and USD→NGN rates
   - Update API key if needed

### Monitoring
4. **View Subscriptions:** `/admin/subscriptions/subscription/`
5. **Monitor Payments:** `/admin/subscriptions/payment/`

## Currency Features

- **Base Currency**: USD (all admin pricing)
- **Auto-Conversion**: Real-time GHS and NGN prices
- **Live Rates**: ExchangeRate-API integration
- **Fallback Rates**: Admin-configurable backup rates
- **Multi-Currency Display**: Frontend shows user's preferred currency

You can now manage all TableTap subscription plans from Django admin with automatic currency conversion!
