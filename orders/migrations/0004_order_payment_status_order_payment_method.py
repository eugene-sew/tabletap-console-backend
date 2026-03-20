from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('orders', '0003_order_customer_phone_order_delivery_address_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='order',
            name='payment_status',
            field=models.CharField(
                choices=[('unpaid', 'Unpaid'), ('partially_paid', 'Partially Paid'), ('paid', 'Paid')],
                default='unpaid',
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name='order',
            name='payment_method',
            field=models.CharField(
                choices=[('cash', 'Cash'), ('mobile_money', 'Mobile Money'), ('card', 'Card'), ('other', 'Other')],
                max_length=20,
                null=True,
                blank=True,
            ),
        ),
    ]
