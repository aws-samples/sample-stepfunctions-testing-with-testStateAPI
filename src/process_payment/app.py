import json
import random

def lambda_handler(event, context):
    """
    Simple payment processing Lambda function
    """
    print(f"Processing payment: {json.dumps(event)}")
    
    # Extract payment information
    order_id = event.get('orderId')
    customer_id = event.get('customerId')
    total_amount = event.get('totalAmount', 0)
    
    # Simulate payment processing
    payment_id = f"pay_{random.randint(100000, 999999)}"
    
    # Simple success/failure simulation (90% success rate)
    success = random.random() > 0.1
    
    if success:
        return {
            'statusCode': 200,
            'paymentStatus': 'SUCCESS',
            'paymentId': payment_id,
            'orderId': order_id,
            'customerId': customer_id,
            'amountProcessed': total_amount,
            'transactionTime': context.aws_request_id if context else 'test-request-id'
        }
    else:
        return {
            'statusCode': 400,
            'paymentStatus': 'FAILED',
            'orderId': order_id,
            'customerId': customer_id,
            'error': 'Payment processing failed'
        }
