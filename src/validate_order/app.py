import json

def lambda_handler(event, context):
    """
    Simple order validation Lambda function
    """
    print(f"Validating order: {json.dumps(event)}")
    
    # Simple validation logic
    order_id = event.get('orderId')
    customer_id = event.get('customerId')
    items = event.get('items', [])
    
    if not order_id:
        return {
            'statusCode': 400,
            'isValid': False,
            'error': 'Missing orderId'
        }
    
    if not customer_id:
        return {
            'statusCode': 400,
            'isValid': False,
            'error': 'Missing customerId'
        }
    
    if not items or len(items) == 0:
        return {
            'statusCode': 400,
            'isValid': False,
            'error': 'No items in order'
        }
    
    # All validations passed
    return {
        'statusCode': 200,
        'isValid': True,
        'orderId': order_id,
        'customerId': customer_id,
        'itemCount': len(items)
    }
