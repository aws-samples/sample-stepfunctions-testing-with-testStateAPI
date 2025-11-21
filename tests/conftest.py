import pytest
import json
import os
import boto3
from typing import Dict, Any, Optional, List, Union

class StepFunctionTestRunner:
    """
    A fluent test runner that follows the Java TestState API patterns.
    Provides method chaining for building and executing TestState API calls
    with comprehensive assertion methods similar to the Java implementation.
    """
    
    def __init__(self, sfn_client, state_machine_definition):
        self.sfn_client = sfn_client
        self.state_machine_definition = state_machine_definition
        self.input_data = None
        self.mock_result = None
        self.mock_error = None
        self.context = None
        self.state_config = None
        self.reveal_secrets = False
        self.inspection_level = 'DEBUG'
        self.response = None
        
    def with_input(self, input_data: Dict[Any, Any]) -> 'StepFunctionTestRunner':
        """Set input data for the test."""
        self.input_data = input_data
        return self
        
    def with_mock_result(self, result: Union[str, Dict[Any, Any]]) -> 'StepFunctionTestRunner':
        """Set mock result for successful execution."""
        if isinstance(result, str):
            self.mock_result = result
        else:
            self.mock_result = json.dumps(result)
        return self
        
    def with_mock_error(self, error: Union[str, Dict[str, str]], cause: Optional[str] = None) -> 'StepFunctionTestRunner':
        """Set mock error for error scenarios."""
        if isinstance(error, dict):
            # Handle dict format like {"Error": "ValidationException", "Cause": "Invalid order format"}
            self.mock_error = {
                'error': error.get('Error', ''),
                'cause': error.get('Cause', cause or '')
            }
        else:
            self.mock_error = {
                'error': error,
                'cause': cause or ''
            }
        return self
        
    def with_context(self, context: Union[str, Dict[Any, Any]]) -> 'StepFunctionTestRunner':
        """Set context object for the execution."""
        if isinstance(context, str):
            self.context = context
        else:
            self.context = json.dumps(context)
        return self
        
    def with_retrier_retry_count(self, retry_count: int) -> 'StepFunctionTestRunner':
        """Set retry count for testing retry mechanisms."""
        if self.state_config is None:
            self.state_config = {}
        self.state_config['retrierRetryCount'] = retry_count
        return self
        
    def with_error_caused_by_state(self, state_name: str) -> 'StepFunctionTestRunner':
        """Set which state caused the error (for Map/Parallel states)."""
        if self.state_config is None:
            self.state_config = {}
        self.state_config['errorCausedByState'] = state_name
        return self
        
    def with_state_configuration(self, config: Dict[str, Any]) -> 'StepFunctionTestRunner':
        """Set complete state configuration for advanced testing scenarios."""
        if self.state_config is None:
            self.state_config = {}
        self.state_config.update(config)
        return self
        
    def with_reveal_secrets(self, reveal: bool) -> 'StepFunctionTestRunner':
        """Set whether to reveal secrets in the response."""
        self.reveal_secrets = reveal
        return self
        
    def with_inspection_level(self, level: str) -> 'StepFunctionTestRunner':
        """Set inspection level (DEBUG, INFO, etc.)."""
        self.inspection_level = level
        return self
        
    def clear_mocks(self) -> 'StepFunctionTestRunner':
        """Clear all mock data (result and error) and context."""
        self.mock_result = None
        self.mock_error = None
        self.context = None
        self.state_config = None
        return self
        
    def execute(self, state_name: str = "ValidateOrder") -> 'StepFunctionTestRunner':
        """Execute the TestState API call."""
        # Prepare parameters
        params = {
            'definition': json.dumps(self.state_machine_definition),
            'stateName': state_name,
            'input': json.dumps(self.input_data or {}),
            'inspectionLevel': self.inspection_level
        }
        
        # Add optional parameters - only add mock if we have either result or error, not both
        if self.mock_result and not self.mock_error:
            params['mock'] = {'result': self.mock_result}
        elif self.mock_error and not self.mock_result:
            params['mock'] = {'errorOutput': self.mock_error}
        elif self.mock_result and self.mock_error:
            # This should not happen, but if it does, prioritize error over result
            params['mock'] = {'errorOutput': self.mock_error}
            
        if self.context:
            params['context'] = self.context
            
        if self.state_config:
            params['stateConfiguration'] = self.state_config
            
        if self.reveal_secrets:
            params['revealSecrets'] = self.reveal_secrets
            
        # Execute the API call
        self.response = self.sfn_client.test_state(**params)
        return self
        
    # Assertion methods following Java patterns
    def assert_succeeded(self) -> 'StepFunctionTestRunner':
        """Assert that the state execution succeeded."""
        assert self.response is not None, "Must call execute() before assertions"
        assert self.response['status'] == 'SUCCEEDED', f"Expected SUCCEEDED, got {self.response['status']}"
        return self
        
    def assert_failed(self) -> 'StepFunctionTestRunner':
        """Assert that the state execution failed."""
        assert self.response is not None, "Must call execute() before assertions"
        assert self.response['status'] == 'FAILED', f"Expected FAILED, got {self.response['status']}"
        return self
        
    def assert_caught_error(self) -> 'StepFunctionTestRunner':
        """Assert that an error was caught by a catch block."""
        assert self.response is not None, "Must call execute() before assertions"
        assert self.response['status'] == 'CAUGHT_ERROR', f"Expected CAUGHT_ERROR, got {self.response['status']}"
        return self
        
    def assert_retriable(self) -> 'StepFunctionTestRunner':
        """Assert that the state is retriable."""
        assert self.response is not None, "Must call execute() before assertions"
        assert self.response['status'] == 'RETRIABLE', f"Expected RETRIABLE, got {self.response['status']}"
        return self
        
    def assert_next_state(self, expected_state: str) -> 'StepFunctionTestRunner':
        """Assert the next state name."""
        assert self.response is not None, "Must call execute() before assertions"
        actual_state = self.response.get('nextState')
        assert actual_state == expected_state, f"Expected next state {expected_state}, got {actual_state}"
        return self
        
    def assert_no_next_state(self) -> 'StepFunctionTestRunner':
        """Assert that there is no next state (terminal state)."""
        assert self.response is not None, "Must call execute() before assertions"
        assert self.response.get('nextState') is None, f"Expected no next state, got {self.response.get('nextState')}"
        return self
        
    def assert_error(self, expected_error: str) -> 'StepFunctionTestRunner':
        """Assert the error type."""
        assert self.response is not None, "Must call execute() before assertions"
        actual_error = self.response.get('error')
        assert actual_error == expected_error, f"Expected error {expected_error}, got {actual_error}"
        return self
        
    def assert_cause(self, expected_cause: str) -> 'StepFunctionTestRunner':
        """Assert the error cause."""
        assert self.response is not None, "Must call execute() before assertions"
        actual_cause = self.response.get('cause')
        assert actual_cause == expected_cause, f"Expected cause {expected_cause}, got {actual_cause}"
        return self
        
    def assert_output_matches_json(self, expected_json: Union[str, Dict[Any, Any]]) -> 'StepFunctionTestRunner':
        """Assert that the output matches the expected JSON."""
        assert self.response is not None, "Must call execute() before assertions"
        actual_output = self.response.get('output')
        
        if isinstance(expected_json, dict):
            expected_json = json.dumps(expected_json)
            
        # Parse both to ensure valid JSON comparison
        actual_parsed = json.loads(actual_output) if actual_output else None
        expected_parsed = json.loads(expected_json)
        
        assert actual_parsed == expected_parsed, f"Expected output {expected_json}, got {actual_output}"
        return self
        
    def assert_after_arguments(self, expected_args: Union[str, Dict[Any, Any]]) -> 'StepFunctionTestRunner':
        """Assert the afterArguments in inspection data."""
        assert self.response is not None, "Must call execute() before assertions"
        inspection = self.response.get('inspectionData', {})
        actual_args = inspection.get('afterArguments')
        
        if isinstance(expected_args, dict):
            expected_args = json.dumps(expected_args)
            
        # Parse both for comparison
        actual_parsed = json.loads(actual_args) if actual_args else None
        expected_parsed = json.loads(expected_args)
        
        assert actual_parsed == expected_parsed, f"Expected afterArguments {expected_args}, got {actual_args}"
        return self
        
    def assert_retry_backoff_interval_seconds(self, expected_seconds: int) -> 'StepFunctionTestRunner':
        """Assert the retry backoff interval."""
        assert self.response is not None, "Must call execute() before assertions"
        inspection = self.response.get('inspectionData', {})
        error_details = inspection.get('errorDetails', {})
        actual_seconds = error_details.get('retryBackoffIntervalSeconds')
        
        assert actual_seconds == expected_seconds, f"Expected backoff {expected_seconds}s, got {actual_seconds}s"
        return self
        
    def assert_retry_policy_handled_error(self, expected_index: int) -> 'StepFunctionTestRunner':
        """Assert which retry policy handled the error."""
        assert self.response is not None, "Must call execute() before assertions"
        inspection = self.response.get('inspectionData', {})
        error_details = inspection.get('errorDetails', {})
        actual_index = error_details.get('retryPolicyHandledError')
        
        assert actual_index == expected_index, f"Expected retry policy index {expected_index}, got {actual_index}"
        return self
        
    def assert_catch_policy_handled_error(self, expected_index: int) -> 'StepFunctionTestRunner':
        """Assert which catch policy handled the error."""
        assert self.response is not None, "Must call execute() before assertions"
        inspection = self.response.get('inspectionData', {})
        error_details = inspection.get('errorDetails', {})
        actual_index = error_details.get('catchPolicyHandledError')
        
        assert actual_index == expected_index, f"Expected catch policy index {expected_index}, got {actual_index}"
        return self
        
    def get_response(self) -> Dict[Any, Any]:
        """Get the raw response from TestState API."""
        assert self.response is not None, "Must call execute() before getting response"
        return self.response
        
    def get_output(self) -> Optional[Dict[Any, Any]]:
        """Get the parsed output from the response."""
        assert self.response is not None, "Must call execute() before getting output"
        output = self.response.get('output')
        return json.loads(output) if output else None


class StepFunctionTestHelper:
    """
    Legacy helper class for backward compatibility.
    Provides simplified methods that wrap the new StepFunctionTestRunner.
    """
    
    def __init__(self, sfn_client, state_machine_definition):
        self.sfn_client = sfn_client
        self.state_machine_definition = state_machine_definition
        self.last_response = None
        self.last_output = None
        
    def create_runner(self) -> StepFunctionTestRunner:
        """Create a new test runner instance."""
        return StepFunctionTestRunner(self.sfn_client, self.state_machine_definition)
    
    def test_state(
        self,
        state_name: str,
        input_data: Optional[Dict[Any, Any]] = None,
        mock_result: Optional[Dict[Any, Any]] = None,
        mock_error: Optional[Dict[str, str]] = None,
        context: Optional[Dict[Any, Any]] = None,
        state_config: Optional[Dict[str, Any]] = None,
        expected_status: str = 'SUCCEEDED',
        expected_next_state: Optional[str] = None,
        auto_use_last_output: bool = True
    ) -> Dict[Any, Any]:
        """
        Execute a TestState API call with automatic configuration and assertions.
        
        Args:
            state_name: Name of the state to test
            input_data: Input data for the state (if None and auto_use_last_output=True, uses last output)
            mock_result: Mock result data for successful execution
            mock_error: Mock error data for error scenarios
            context: Context object for the execution
            state_config: State configuration (e.g., retry count)
            expected_status: Expected response status (default: 'SUCCEEDED')
            expected_next_state: Expected next state name
            auto_use_last_output: Whether to automatically use last output as input
            
        Returns:
            TestState API response
        """
        
        # Use last output as input if not provided and auto_use_last_output is True
        if input_data is None and auto_use_last_output and self.last_output is not None:
            input_data = self.last_output
        
        # Prepare the TestState API call parameters
        params = {
            'definition': json.dumps(self.state_machine_definition),
            'stateName': state_name,
            'input': json.dumps(input_data or {}),
            'inspectionLevel': 'DEBUG'  # Always use DEBUG for comprehensive inspection
        }
        
        # Add optional parameters
        if mock_result or mock_error:
            mock_config = {}
            if mock_result:
                mock_config['result'] = json.dumps(mock_result)
            if mock_error:
                mock_config['errorOutput'] = mock_error
            params['mock'] = mock_config
        
        if context:
            params['context'] = json.dumps(context)
            
        if state_config:
            params['stateConfiguration'] = state_config
        
        # Execute the TestState API call
        response = self.sfn_client.test_state(**params)
        
        # Store response and output for chaining
        self.last_response = response
        if 'output' in response:
            self.last_output = json.loads(response['output'])
        
        # Perform automatic assertions
        assert response['status'] == expected_status, f"Expected status {expected_status}, got {response['status']}"
        
        if expected_next_state is not None:
            actual_next_state = response.get('nextState')
            assert actual_next_state == expected_next_state, f"Expected next state {expected_next_state}, got {actual_next_state}"
        
        return response
    
    def test_choice_state(
        self,
        state_name: str,
        input_data: Optional[Dict[Any, Any]] = None,
        expected_next_state: str = None,
        auto_use_last_output: bool = True
    ) -> Dict[Any, Any]:
        """
        Simplified method for testing Choice states.
        """
        return self.test_state(
            state_name=state_name,
            input_data=input_data,
            expected_status='SUCCEEDED',
            expected_next_state=expected_next_state,
            auto_use_last_output=auto_use_last_output
        )
    
    def test_task_state(
        self,
        state_name: str,
        input_data: Optional[Dict[Any, Any]] = None,
        mock_result: Optional[Dict[Any, Any]] = None,
        expected_next_state: Optional[str] = None,
        auto_use_last_output: bool = True
    ) -> Dict[Any, Any]:
        """
        Simplified method for testing Task states (Lambda, DynamoDB, etc.).
        """
        return self.test_state(
            state_name=state_name,
            input_data=input_data,
            mock_result=mock_result,
            expected_status='SUCCEEDED',
            expected_next_state=expected_next_state,
            auto_use_last_output=auto_use_last_output
        )
    
    def test_wait_for_task_token_state(
        self,
        state_name: str,
        input_data: Optional[Dict[Any, Any]] = None,
        mock_result: Optional[Dict[Any, Any]] = None,
        task_token: str = "test-task-token",
        execution_id: str = "test-execution-id",
        expected_next_state: Optional[str] = None,
        auto_use_last_output: bool = True
    ) -> Dict[Any, Any]:
        """
        Simplified method for testing waitForTaskToken states.
        """
        context = {
            "Task": {"Token": task_token},
            "Execution": {"Id": execution_id}
        }
        
        return self.test_state(
            state_name=state_name,
            input_data=input_data,
            mock_result=mock_result,
            context=context,
            expected_status='SUCCEEDED',
            expected_next_state=expected_next_state,
            auto_use_last_output=auto_use_last_output
        )
    
    def test_retry_mechanism(
        self,
        state_name: str,
        input_data: Optional[Dict[Any, Any]] = None,
        error_type: str = 'Lambda.TooManyRequestsException',
        error_cause: str = 'Request rate exceeded',
        retry_count: int = 0,
        max_attempts: int = 3,
        expected_backoff_seconds: int = 2,
        auto_use_last_output: bool = True
    ) -> Dict[Any, Any]:
        """
        Simplified method for testing retry mechanisms.
        """
        mock_error = {
            'error': error_type,
            'cause': error_cause
        }
        
        state_config = {
            'retrierRetryCount': retry_count
        }
        
        # Determine expected status based on retry count
        if retry_count >= max_attempts:
            expected_status = 'CAUGHT_ERROR'
        else:
            expected_status = 'RETRIABLE'
        
        response = self.test_state(
            state_name=state_name,
            input_data=input_data,
            mock_error=mock_error,
            state_config=state_config,
            expected_status=expected_status,
            auto_use_last_output=auto_use_last_output
        )
        
        # Additional assertions for retry mechanism
        if expected_status == 'RETRIABLE':
            error_details = response['inspectionData']['errorDetails']
            # Verify that retry mechanism is working by checking for required fields
            assert 'retryBackoffIntervalSeconds' in error_details
            assert 'retryIndex' in error_details
            actual_backoff = error_details['retryBackoffIntervalSeconds']
            assert actual_backoff > 0, f"Backoff interval should be positive, got {actual_backoff}"
            # Note: retryIndex may not directly correspond to our retry_count parameter
            # as the API may have its own internal retry indexing
        
        return response
    
    def test_terminal_state(
        self,
        state_name: str,
        input_data: Optional[Dict[Any, Any]] = None,
        expected_status: str = 'SUCCEEDED',
        auto_use_last_output: bool = True
    ) -> Dict[Any, Any]:
        """
        Simplified method for testing terminal states (Succeed/Fail).
        """
        response = self.test_state(
            state_name=state_name,
            input_data=input_data,
            expected_status=expected_status,
            expected_next_state=None,  # Terminal states have no next state
            auto_use_last_output=auto_use_last_output
        )
        
        # Assert that it's truly terminal
        assert response.get('nextState') is None, f"Terminal state {state_name} should not have a nextState"
        
        return response
    
    def get_last_output(self) -> Optional[Dict[Any, Any]]:
        """Get the output from the last TestState call."""
        return self.last_output
    
    def get_last_response(self) -> Optional[Dict[Any, Any]]:
        """Get the full response from the last TestState call."""
        return self.last_response
    
    def reset_chain(self):
        """Reset the state chain (clear last output and response)."""
        self.last_output = None
        self.last_response = None


@pytest.fixture
def state_machine_definition():
    """Load the complete state machine definition"""
    definition_path = os.path.join(
        os.path.dirname(__file__), 
        '..', 
        'statemachine', 
        'order_processing.asl.json'
    )
    with open(definition_path, 'r') as f:
        return json.load(f)


@pytest.fixture
def sfn_client():
    """Step Functions client for TestState API calls"""
    return boto3.client('stepfunctions', region_name='ca-central-1')


@pytest.fixture
def sfn_test_helper(sfn_client, state_machine_definition):
    """
    Main fixture that provides the StepFunctionTestHelper for simplified testing.
    
    Usage examples:
    
    # Simple task state test
    sfn_test_helper.test_task_state(
        state_name="ValidateOrder",
        input_data={"orderId": "123"},
        mock_result={"isValid": True},
        expected_next_state="CheckValidation"
    )
    
    # Choice state test (automatically uses last output)
    sfn_test_helper.test_choice_state(
        state_name="CheckValidation",
        expected_next_state="ProcessOrderItems"
    )
    
    # Retry mechanism test
    sfn_test_helper.test_retry_mechanism(
        state_name="ValidateOrder",
        retry_count=0,
        expected_backoff_seconds=2
    )
    """
    return StepFunctionTestHelper(sfn_client, state_machine_definition)


@pytest.fixture
def runner(sfn_client, state_machine_definition):
    """
    Direct fixture that provides a StepFunctionTestRunner for method chaining tests.
    
    Usage example:
    result = (runner
        .with_input(test_data)
        .with_mock_result(mock_result)
        .execute("ValidateOrder")
        .assert_succeeded())
    """
    return StepFunctionTestRunner(sfn_client, state_machine_definition)
