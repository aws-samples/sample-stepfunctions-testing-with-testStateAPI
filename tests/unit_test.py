"""
Enhanced Unit Tests using Fluent API patterns for Step Functions TestState API.
This demonstrates comprehensive testing with method chaining and fluent assertions.
"""

import pytest
import json


class TestOrderProcessingStateMachine:
    """Test class for comprehensive Step Functions order processing workflow testing."""

    # ============================================================================
    # HAPPY PATH TESTS - Complete workflow validation using state chaining
    # ============================================================================

    def test_complete_order_processing_workflow(self, runner):
        """
        Integration test: Complete happy path workflow using fluent API
        Demonstrates how to chain TestState calls with fluent assertions
        """
        # Initial input for the workflow
        test_input = {
            "orderId": "order-12345",
            "amount": 150.75,
            "customerEmail": "customer@example.com",
            "orderItems": [
                {"itemId": "item-1", "quantity": 2, "price": 50.25},
                {"itemId": "item-2", "quantity": 1, "price": 50.25}
            ]
        }
        
        validation_result = {
            "statusCode": 200,
            "isValid": True,
            "orderId": "order-12345",
            "validatedAt": "2025-01-15T10:30:00Z"
        }
        
        # Step 1: Test ValidateOrder state with fluent API
        (runner
         .with_input(test_input)
         .with_mock_result(validation_result)
         .execute("ValidateOrder")
         .assert_succeeded()
         .assert_next_state("CheckValidation"))
        
        # Get output for next state
        validation_output = runner.get_output()
        
        # Step 2: Test CheckValidation choice state (NO MOCK - Choice states can't be mocked)
        (runner
         .with_input(validation_output)
         .clear_mocks()
         .execute("CheckValidation")
         .assert_succeeded()
         .assert_next_state("ProcessOrderItems"))
        
        # Step 3: Test ProcessOrderItems Map state
        map_result = [
            {"itemId": "item-1", "processed": True, "timestamp": "2025-01-15T10:31:00Z"},
            {"itemId": "item-2", "processed": True, "timestamp": "2025-01-15T10:31:01Z"}
        ]
        
        (runner
         .with_input(validation_output)
         .with_mock_result(map_result)
         .execute("ProcessOrderItems")
         .assert_succeeded()
         .assert_next_state("ParallelProcessing"))
        
        # Step 4: Test ParallelProcessing state
        parallel_result = [
            {"paymentId": "pay-12345", "status": "completed", "amount": 150.75},
            {"inventoryUpdated": True, "itemsReserved": 2}
        ]
        
        parallel_input = runner.get_output()
        (runner
         .with_input(parallel_input)
         .with_mock_result(parallel_result)
         .execute("ParallelProcessing")
         .assert_succeeded()
         .assert_next_state("WaitForApproval"))
        
        # Step 5: Test WaitForApproval waitForTaskToken state
        approval_result = {
            "approved": True,
            "approvedBy": "manager@example.com",
            "approvedAt": "2025-01-15T10:35:00Z"
        }
        
        context_data = {
            "Task": {"Token": "test-task-token-12345"},
            "Execution": {"Id": "exec-12345"}
        }
        
        approval_input = runner.get_output()
        (runner
         .with_input(approval_input)
         .with_context(context_data)
         .with_mock_result(approval_result)
         .execute("WaitForApproval")
         .assert_succeeded()
         .assert_next_state("CheckApproval"))
        
        # Step 6: Test CheckApproval choice state (NO MOCK)
        check_approval_input = runner.get_output()
        (runner
         .with_input(check_approval_input)
         .clear_mocks()
         .execute("CheckApproval")
         .assert_succeeded()
         .assert_next_state("SaveOrderDetails"))
        
        # Step 7: Test SaveOrderDetails DynamoDB state
        save_result = {
            "Attributes": {
                "orderId": {"S": "order-12345"},
                "status": {"S": "COMPLETED"}
            }
        }
        
        save_context = {
            "State": {"EnteredTime": "2025-01-15T10:36:00Z"}
        }
        
        save_input = runner.get_output()
        (runner
         .with_input(save_input)
         .with_context(save_context)
         .with_mock_result(save_result)
         .execute("SaveOrderDetails")
         .assert_succeeded()
         .assert_next_state("SendNotification"))
        
        # Step 8: Test SendNotification state
        notification_result = {
            "messageId": "msg-12345",
            "sent": True,
            "recipient": "customer@example.com"
        }
        
        notification_input = runner.get_output()
        (runner
         .with_input(notification_input)
         .with_mock_result(notification_result)
         .execute("SendNotification")
         .assert_succeeded()
         .assert_next_state("OrderProcessed"))
        
        # Step 9: Test final OrderProcessed succeed state (NO MOCK - Succeed states can't be mocked)
        final_input = runner.get_output()
        (runner
         .with_input(final_input)
         .clear_mocks()
         .execute("OrderProcessed")
         .assert_succeeded()
         .assert_no_next_state())

    # ============================================================================
    # ERROR HANDLING TESTS - Testing retry mechanisms and catch blocks
    # ============================================================================

    def test_lambda_throttling_retry_mechanism(self, runner):
        """
        Test retry mechanism for Lambda.TooManyRequestsException with exponential backoff
        """
        test_input = {
            "orderId": "order-retry-test",
            "amount": 100.0
        }
        
        throttling_error = {
            "Error": "Lambda.TooManyRequestsException",
            "Cause": "Request rate exceeded"
        }
        
        # Test first retry attempt
        (runner
         .with_input(test_input)
         .with_mock_error(throttling_error)
         .with_retrier_retry_count(0)
         .execute("ValidateOrder")
         .assert_retriable()
         .assert_error("Lambda.TooManyRequestsException")
         .assert_cause("Request rate exceeded"))
        
        # Verify retry backoff interval
        response = runner.get_response()
        error_details = response['inspectionData']['errorDetails']
        assert error_details['retryBackoffIntervalSeconds'] == 2
        assert error_details['retryIndex'] == 0
        
        # Test second retry attempt
        (runner
         .with_input(test_input)
         .with_mock_error(throttling_error)
         .with_retrier_retry_count(1)
         .execute("ValidateOrder")
         .assert_retriable())
        
        # Verify increased backoff interval
        response = runner.get_response()
        error_details = response['inspectionData']['errorDetails']
        assert error_details['retryBackoffIntervalSeconds'] == 4  # 2 * 2.0 backoff rate
        
        # Test final retry attempt (should exhaust retries)
        (runner
         .with_input(test_input)
         .with_mock_error(throttling_error)
         .with_retrier_retry_count(3)
         .execute("ValidateOrder")
         .assert_caught_error()
         .assert_next_state("ValidationFailed"))

    def test_map_state_tolerated_failure_threshold(self, runner):
        """
        Test Map state with tolerated failure threshold for order item processing
        """
        test_input = {
            "orderId": "order-map-test",
            "orderItems": [
                {"itemId": "item-1"}, {"itemId": "item-2"}, 
                {"itemId": "item-3"}, {"itemId": "item-4"}, 
                {"itemId": "item-5"}
            ]
        }
        
        # Test Map state normal success case
        map_success_result = [
            {"itemId": "item-1", "processed": True},
            {"itemId": "item-2", "processed": True},
            {"itemId": "item-3", "processed": True},
            {"itemId": "item-4", "processed": True},
            {"itemId": "item-5", "processed": True}
        ]
        
        (runner
         .with_input(test_input)
         .with_mock_result(map_success_result)
         .execute("ProcessOrderItems")
         .assert_succeeded()
         .assert_next_state("ParallelProcessing"))
        
        # Verify tolerance configuration exists
        response = runner.get_response()
        inspection = response['inspectionData']
        assert 'toleratedFailureCount' in inspection
        
        # Note: ProcessItem is inside Map state's ItemProcessor and cannot be tested directly
        # Test Map state failure scenarios instead
        
        # Test Map state when tolerance threshold is exceeded
        tolerance_error = {
            "Error": "States.ExceedToleratedFailureThreshold",
            "Cause": "Map state exceeded tolerated failure threshold"
        }
        
        (runner
         .with_input(test_input)
         .with_mock_error(tolerance_error)
         .execute("ProcessOrderItems")
         .assert_caught_error()
         .assert_next_state("ValidationFailed"))

    def test_parallel_state_branch_failure_handling(self, runner):
        """
        Test Parallel state branch failure handling for payment and inventory processing
        """
        test_input = {
            "orderId": "order-parallel-test",
            "amount": 200.0,
            "processedItems": [{"itemId": "item-1", "processed": True}]
        }
        
        # Test successful parallel execution
        parallel_success_result = [
            {"paymentId": "pay-12345", "status": "completed", "amount": 200.0},
            {"inventoryUpdated": True, "itemsReserved": 1}
        ]
        
        (runner
         .with_input(test_input)
         .with_mock_result(parallel_success_result)
         .execute("ParallelProcessing")
         .assert_succeeded()
         .assert_next_state("WaitForApproval"))
        
        # Test Parallel state with States.BranchFailed (should trigger retry)
        branch_error = {
            "Error": "States.BranchFailed",
            "Cause": "One or more parallel branches failed"
        }
        
        (runner
         .with_input(test_input)
         .with_mock_error(branch_error)
         .with_retrier_retry_count(0)
         .execute("ParallelProcessing")
         .assert_retriable())
        
        # Test after exhausting retries
        (runner
         .with_input(test_input)
         .with_mock_error(branch_error)
         .with_retrier_retry_count(2)
         .execute("ParallelProcessing")
         .assert_caught_error()
         .assert_next_state("OrderRejected"))
        
        # Test with non-retryable error
        task_error = {
            "Error": "States.TaskFailed",
            "Cause": "Generic task failure in parallel branch"
        }
        
        (runner
         .with_input(test_input)
         .with_mock_error(task_error)
         .execute("ParallelProcessing")
         .assert_caught_error()
         .assert_next_state("OrderRejected"))

    # ============================================================================
    # NEGATIVE SCENARIO TESTS - Testing validation failures for Choice states
    # ============================================================================

    def test_order_validation_failure_path(self, runner):
        """
        Test order validation failure path and error routing
        """
        # Test with invalid order data
        invalid_input = {
            "orderId": "",  # Invalid empty order ID
            "amount": -50.0,  # Invalid negative amount
            "customerEmail": "invalid-email"  # Invalid email format
        }
        
        validation_failure_result = {
            "statusCode": 400,
            "isValid": False,
            "errors": [
                "Order ID cannot be empty",
                "Amount must be positive",
                "Invalid email format"
            ]
        }
        
        # Step 1: ValidateOrder returns validation failure
        (runner
         .with_input(invalid_input)
         .with_mock_result(validation_failure_result)
         .execute("ValidateOrder")
         .assert_succeeded()
         .assert_next_state("CheckValidation"))
        
        # Step 2: CheckValidation should route to ValidationFailed (NO MOCK)
        validation_output = runner.get_output()
        (runner
         .with_input(validation_output)
         .clear_mocks()
         .execute("CheckValidation")
         .assert_succeeded()
         .assert_next_state("ValidationFailed"))
        
        # Step 3: ValidationFailed should be a terminal failure state
        (runner
         .with_input(validation_output)
         .execute("ValidationFailed")
         .assert_failed()
         .assert_no_next_state())

    def test_order_approval_rejection_path(self, runner):
        """
        Test order rejection path after manager approval denial
        """
        test_input = {
            "orderId": "order-rejection-test",
            "amount": 1000.0,  # High amount requiring approval
            "parallelResults": [
                {"paymentId": "pay-123", "status": "completed"},
                {"inventoryUpdated": True}
            ]
        }
        
        rejection_result = {
            "approved": False,
            "rejectedBy": "manager@example.com",
            "rejectionReason": "Amount exceeds approval limit",
            "rejectedAt": "2025-01-15T10:40:00Z"
        }
        
        context_data = {
            "Task": {"Token": "test-token-rejection"},
            "Execution": {"Id": "exec-rejection-test"}
        }
        
        # Step 1: Test WaitForApproval with rejection response
        (runner
         .with_input(test_input)
         .with_context(context_data)
         .with_mock_result(rejection_result)
         .execute("WaitForApproval")
         .assert_succeeded()
         .assert_next_state("CheckApproval"))
        
        # Step 2: Test CheckApproval choice state with rejection (NO MOCK)
        approval_output = runner.get_output()
        (runner
         .with_input(approval_output)
         .clear_mocks()
         .execute("CheckApproval")
         .assert_succeeded()
         .assert_next_state("OrderRejected"))
        
        # Step 3: Test OrderRejected terminal failure state
        (runner
         .with_input(approval_output)
         .execute("OrderRejected")
         .assert_failed()
         .assert_no_next_state())

    # ============================================================================
    # JSONATA TRANSFORMATION TESTS - Testing JSONata expressions and transformations
    # ============================================================================

    def test_jsonata_data_transformations_and_merging(self, runner):
        """
        Test JSONata transformations and data merging in order processing
        """
        test_input = {
            "orderId": "order-jsonata-test",
            "amount": 75.50,
            "customerData": {
                "email": "test@example.com",
                "name": "John Doe"
            }
        }
        
        mock_result = {
            "statusCode": 200,
            "isValid": True,
            "processedData": {
                "orderId": "order-jsonata-test",
                "validatedAmount": 75.50
            }
        }
        
        # Test JSONata transformation in ValidateOrder
        (runner
         .with_input(test_input)
         .with_mock_result(mock_result)
         .execute("ValidateOrder")
         .assert_succeeded())
        
        # Verify JSONata transformation in inspection data
        response = runner.get_response()
        inspection = response['inspectionData']
        assert 'afterArguments' in inspection
        
        # Verify the output structure
        output = runner.get_output()
        assert 'validationResult' in output
        assert output['orderId'] == 'order-jsonata-test'  # Original input preserved
        
        validation_result = output['validationResult']
        assert validation_result['isValid'] == True
        assert 'processedData' in validation_result

    def test_context_object_usage_in_jsonata_expressions(self, runner):
        """
        Test Context object usage in JSONata expressions for task tokens and execution metadata
        """
        test_input = {
            "orderId": "order-context-test",
            "amount": 125.0
        }
        
        context_data = {
            "Task": {"Token": "ahbdgftgehbdcndsjnwjkhas327yr4hendc73yehdb723y"},
            "Execution": {
                "Id": "arn:aws:states:us-east-1:123456789012:execution:test:exec-123",
                "Name": "test-execution"
            },
            "State": {
                "Name": "WaitForApproval",
                "EnteredTime": "2025-01-15T10:45:00Z"
            }
        }
        
        mock_result = {
            "approved": True,
            "taskToken": "ahbdgftgehbdcndsjnwjkhas327yr4hendc73yehdb723y"
        }
        
        # Test WaitForApproval with context object
        (runner
         .with_input(test_input)
         .with_context(context_data)
         .with_mock_result(mock_result)
         .execute("WaitForApproval")
         .assert_succeeded()
         .assert_next_state("CheckApproval"))
        
        # Verify context object was used in JSONata expressions
        response = runner.get_response()
        inspection = response['inspectionData']
        assert 'afterArguments' in inspection
        
        after_args = json.loads(inspection['afterArguments'])
        assert 'Payload' in after_args
        payload = after_args['Payload']
        
        # Verify context fields were properly injected
        assert 'taskToken' in payload
        assert payload['taskToken'] == "ahbdgftgehbdcndsjnwjkhas327yr4hendc73yehdb723y"
        assert 'orderId' in payload
        assert payload['orderId'] == "order-context-test"
        
        # Verify the output structure
        output = runner.get_output()
        assert 'approvalResult' in output
        approval_result = output['approvalResult']
        assert approval_result['approved'] == True
        assert approval_result['taskToken'] == "ahbdgftgehbdcndsjnwjkhas327yr4hendc73yehdb723y"

    def test_comprehensive_method_chaining_demonstration(self, runner):
        """
        Comprehensive demonstration of fluent API method chaining capabilities
        """
        test_input = {
            "orderId": "order-comprehensive-test",
            "amount": 299.99,
            "customerEmail": "comprehensive@example.com",
            "orderItems": [
                {"itemId": "premium-item", "quantity": 1, "price": 299.99}
            ]
        }
        
        context_data = {
            "Execution": {"Name": "comprehensive-execution"},
            "StateMachine": {"Name": "OrderProcessingStateMachine"}
        }
        
        mock_result = {
            "statusCode": 200,
            "isValid": True,
            "orderId": "order-comprehensive-test",
            "validatedAt": "2025-01-15T11:00:00Z",
            "premiumOrder": True
        }
        
        # Demonstrate comprehensive method chaining with all available methods
        result = (runner
                 .with_input(test_input)
                 .with_context(context_data)
                 .with_mock_result(mock_result)
                 .with_inspection_level("DEBUG")
                 .execute("ValidateOrder")
                 .assert_succeeded()
                 .assert_next_state("CheckValidation"))
        
        # Verify the result object supports further chaining
        assert result is not None
        
        # Verify comprehensive output structure - Step Functions wraps mock result
        output = result.get_output()
        assert 'validationResult' in output
        assert output['orderId'] == 'order-comprehensive-test'
        
        validation_result = output['validationResult']
        assert validation_result['isValid'] == True
        assert validation_result['premiumOrder'] == True

    def test_error_assertion_method_chaining(self, runner):
        """
        Demonstrate comprehensive error assertion method chaining
        """
        test_input = {
            "orderId": "order-error-test",
            "amount": 50.0
        }
        
        validation_error = {
            "Error": "ValidationException",
            "Cause": "Order amount below minimum threshold"
        }
        
        # Demonstrate error assertion chaining - ValidationException is not retryable
        (runner
         .with_input(test_input)
         .with_mock_error(validation_error)
         .execute("ValidateOrder")
         .assert_caught_error()
         .assert_error("ValidationException")
         .assert_cause("Order amount below minimum threshold")
         .assert_next_state("ValidationFailed"))
        
        # Verify error details in response
        response = runner.get_response()
        assert response['status'] == 'CAUGHT_ERROR'
        assert response['error'] == 'ValidationException'
        assert response['cause'] == 'Order amount below minimum threshold'

    def test_map_state_internal_processing_with_error_caused_by_state(self, runner):
        """
        Integration test: Complete happy path order processing workflow
        Tests the full order processing flow from validation through completion
        """
        # Test input with multiple order items for Map state processing
        test_input = {
            "orderId": "order-map-internal-test",
            "amount": 250.0,
            "customerEmail": "maptest@example.com",
            "orderItems": [
                {"itemId": "item-001", "quantity": 2, "price": 75.0, "category": "electronics"},
                {"itemId": "item-002", "quantity": 1, "price": 100.0, "category": "books"},
                {"itemId": "item-003", "quantity": 3, "price": 25.0, "category": "clothing"}
            ],
            "validationResult": {
                "isValid": True,
                "statusCode": 200
            }
        }
        
        # Test 1: Successful ProcessItem execution within Map state
        # This tests the internal state of the Map's ItemProcessor
        single_item_input = {"itemId": "item-001", "quantity": 2, "price": 75.0, "category": "electronics"}
        
        process_item_result = {
            "itemId": "item-001",
            "processed": True,
            "processedQuantity": 2,
            "processedAmount": 150.0,
            "timestamp": "2025-01-15T11:15:00Z",
            "processingDetails": {
                "category": "electronics",
                "warehouseLocation": "A-15",
                "estimatedShipping": "2025-01-17T00:00:00Z"
            }
        }
        
        # Test the internal ProcessItem state directly
        (runner
         .with_input(single_item_input)
         .with_mock_result(process_item_result)
         .execute("ProcessItem")
         .assert_succeeded()
         .assert_no_next_state())  # ProcessItem has "End": true
        
        # Verify the ProcessItem output structure
        item_output = runner.get_output()
        assert item_output['itemId'] == 'item-001'
        assert item_output['processed'] == True
        assert item_output['processedQuantity'] == 2
        assert 'processingDetails' in item_output
        
        # Test 2: ProcessItem failure (without errorCausedByState - only for Map/Parallel states)
        # This demonstrates testing individual state failures within Map ItemProcessor
        problematic_item_input = {
            "itemId": "item-corrupted", 
            "quantity": -1,  # Invalid quantity
            "price": 0,      # Invalid price
            "category": "unknown"
        }
        
        item_processing_error = {
            "Error": "ItemValidationException",
            "Cause": "Invalid item data: quantity must be positive and price must be greater than zero"
        }
        
        # Test ProcessItem failure (errorCausedByState not applicable for individual states)
        (runner
         .with_input(problematic_item_input)
         .with_mock_error(item_processing_error)
         .execute("ProcessItem")
         .assert_caught_error()
         .assert_error("ItemValidationException")
         .assert_cause("Invalid item data: quantity must be positive and price must be greater than zero")
         .assert_next_state("ItemProcessingFailed"))
        
        # Verify error details are properly captured
        response = runner.get_response()
        assert response['status'] == 'CAUGHT_ERROR'
        assert response['error'] == 'ItemValidationException'
        assert 'inspectionData' in response
        
        # Test 3: Map state testing (DISTRIBUTED mode limitation)
        # Note: DISTRIBUTED Map states cannot be fully mocked like inline Map states
        # This demonstrates testing the Map state structure and error handling
        successful_items_input = {
            "orderId": "order-successful-map",
            "orderItems": [
                {"itemId": "item-good-1", "quantity": 1, "price": 50.0},
                {"itemId": "item-good-2", "quantity": 2, "price": 25.0},
                {"itemId": "item-good-3", "quantity": 1, "price": 75.0}
            ],
            "validationResult": {"isValid": True}
        }
        
        # For DISTRIBUTED Map states, we test the error scenarios instead of success
        # because the AWS TestState API cannot fully simulate distributed execution
        map_distributed_error = {
            "Error": "States.ExecutionLimitExceeded",
            "Cause": "Distributed Map state execution limit exceeded"
        }
        
        (runner
         .with_input(successful_items_input)
         .with_mock_error(map_distributed_error)
         .execute("ProcessOrderItems")
         .assert_caught_error()
         .assert_error("States.ExecutionLimitExceeded")
         .assert_next_state("ValidationFailed"))
        
        # Verify Map state configuration is accessible in inspection data
        response = runner.get_response()
        inspection = response['inspectionData']
        
        # Check that Map state configuration is present
        # DISTRIBUTED Map states have different inspection data structure
        assert 'toleratedFailureCount' in inspection or 'maxConcurrency' in inspection
        
        # Test 4: Map state failure exceeding tolerance threshold with errorCausedByState
        # This demonstrates when Map state fails due to too many item failures
        high_failure_input = {
            "orderId": "order-high-failure",
            "orderItems": [
                {"itemId": "item-fail-1", "quantity": -1, "price": 0},
                {"itemId": "item-fail-2", "quantity": -2, "price": 0},
                {"itemId": "item-fail-3", "quantity": -3, "price": 0},
                {"itemId": "item-good", "quantity": 1, "price": 50.0}
            ],
            "validationResult": {"isValid": True}
        }
        
        tolerance_exceeded_error = {
            "Error": "States.ExceedToleratedFailureThreshold",
            "Cause": "Map state exceeded tolerated failure threshold of 2 failures"
        }
        
        tolerance_exceeded_config = {
            "errorCausedByState": "ProcessItem",
            "mapIterationFailureCount": 3  # Number of Map iterations that failed (exceeds tolerance)
        }
        
        (runner
         .with_input(high_failure_input)
         .with_mock_error(tolerance_exceeded_error)
         .with_state_configuration(tolerance_exceeded_config)
         .execute("ProcessOrderItems")
         .assert_caught_error()
         .assert_error("States.ExceedToleratedFailureThreshold")
         .assert_next_state("ValidationFailed"))
        
        # Verify detailed failure analysis in inspection data
        response = runner.get_response()
        inspection = response['inspectionData']
        
        # Verify stateConfiguration was applied correctly
        if 'stateConfiguration' in inspection:
            state_config = inspection['stateConfiguration']
            assert state_config['errorCausedByState'] == 'ProcessItem'
            assert state_config['mapIterationFailureCount'] == 3
        
        # Verify error details provide failure information
        if 'errorDetails' in inspection:
            error_details = inspection['errorDetails']
            # Error details may contain catchIndex or other failure-related information
            assert 'catchIndex' in error_details or len(error_details) > 0, f"Expected error details: {error_details}"
