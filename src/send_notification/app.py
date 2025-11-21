import json

def lambda_handler(event, context):
    """Send notification after successful order processing"""
    
    order_id = event.get('orderId')
    customer_email = event.get('customerEmail', 'customer@example.com')
    
    # Simulate notification sending
    # In real scenario, this would integrate with SNS, SES, or other notification service
    
    return {
        'statusCode': 200,
        'notificationSent': True,
        'orderId': order_id,
        'recipient': customer_email,
        'message': f'Order confirmation sent to {customer_email}'
    }