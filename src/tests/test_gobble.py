from unittest.mock import patch, MagicMock, Mock
import requests

from gobble import connect, process_events, client_thread


class TestConnect:
    """Test the connect function"""

    @patch("gobble.requests.get")
    def test_connect_basic(self, mock_get):
        """Test that connect makes a proper request to MBTA API"""
        mock_response = Mock()
        mock_get.return_value = mock_response

        routes = {"Red", "Blue", "Orange"}
        result = connect(routes)

        # Verify request was made
        mock_get.assert_called_once()
        call_args = mock_get.call_args

        # Verify URL contains routes
        url = call_args[0][0]
        assert "api-v3.mbta.com/vehicles" in url
        assert "filter[route]" in url

        # Verify headers
        headers = call_args[1]["headers"]
        assert "X-API-KEY" in headers
        assert "Accept" in headers
        assert headers["Accept"] == "text/event-stream"

        # Verify streaming is enabled
        assert call_args[1]["stream"] is True

        # Verify result is the response
        assert result == mock_response

    @patch("gobble.requests.get")
    def test_connect_single_route(self, mock_get):
        """Test connect with a single route"""
        mock_response = Mock()
        mock_get.return_value = mock_response

        routes = {"1"}
        result = connect(routes)
        print(result)

        mock_get.assert_called_once()
        url = mock_get.call_args[0][0]
        assert "filter[route]=1" in url


class TestProcessEvents:
    """Test the process_events function"""

    def test_process_events_handles_update_events(self):
        """Test that process_events processes update events"""
        # Create mock SSE client
        mock_client = MagicMock()
        mock_trips_state = MagicMock()

        # Create mock events
        mock_event_1 = Mock()
        mock_event_1.event = "update"
        mock_event_1.data = '{"data": {"type": "vehicle", "id": "y1234"}}'

        mock_event_2 = Mock()
        mock_event_2.event = "update"
        mock_event_2.data = '{"data": {"type": "vehicle", "id": "y5678"}}'

        # Mock the events() method to return two events then stop
        def mock_events():
            yield mock_event_1
            yield mock_event_2
            return  # Generator should return, not raise StopIteration

        mock_client.events = mock_events

        with patch("gobble.process_event") as mock_process_event:
            process_events(mock_client, mock_trips_state)

            # Verify process_event was called for update events
            assert mock_process_event.call_count == 2

    def test_process_events_handles_reset_events(self):
        """Test that process_events handles reset events with list of updates"""
        mock_client = MagicMock()
        mock_trips_state = MagicMock()

        mock_event = Mock()
        mock_event.event = "reset"
        # Reset events contain a list of vehicle updates
        mock_event.data = '[{"data": {"type": "vehicle", "id": "v1"}}, {"data": {"type": "vehicle", "id": "v2"}}]'

        def mock_events():
            yield mock_event
            return  # Generator should return, not raise StopIteration

        mock_client.events = mock_events

        with patch("gobble.process_event") as mock_process_event:
            process_events(mock_client, mock_trips_state)

            # Verify process_event was called for each update in reset
            assert mock_process_event.call_count == 2

    def test_process_events_handles_add_events(self):
        """Test that process_events processes add events same as update"""
        mock_client = MagicMock()
        mock_trips_state = MagicMock()

        mock_event = Mock()
        mock_event.event = "add"
        mock_event.data = '{"data": {"type": "vehicle", "id": "y1234"}}'

        def mock_events():
            yield mock_event
            return  # Generator should return, not raise StopIteration

        mock_client.events = mock_events

        with patch("gobble.process_event") as mock_process_event:
            process_events(mock_client, mock_trips_state)

            # Verify process_event was called for add event
            mock_process_event.assert_called_once()


class TestClientThread:
    """Test the client_thread function"""

    @patch("gobble.sseclient.SSEClient")
    @patch("gobble.connect")
    @patch("gobble.process_events")
    def test_client_thread_creates_connection(self, mock_process_events, mock_connect, mock_sse_client):
        """Test that client_thread creates SSE connection and processes events"""
        mock_response = Mock()
        mock_connect.return_value = mock_response

        mock_client = Mock()
        mock_sse_client.return_value = mock_client

        # Make process_events raise an exception to break the infinite loop
        mock_process_events.side_effect = KeyboardInterrupt()

        routes = {"Red", "Blue"}

        try:
            client_thread(routes)
        except KeyboardInterrupt:
            pass

        # Verify connection was established
        mock_connect.assert_called_with(routes)

        # Verify SSE client was created
        mock_sse_client.assert_called_with(mock_response)

        # Verify process_events was called
        mock_process_events.assert_called_once()

    @patch("gobble.sseclient.SSEClient")
    @patch("gobble.connect")
    @patch("gobble.process_events")
    @patch("gobble.time.sleep")
    def test_client_thread_retries_on_error(self, mock_sleep, mock_process_events, mock_connect, mock_sse_client):
        """Test that client_thread retries on connection errors"""
        mock_response = Mock()
        mock_connect.return_value = mock_response

        mock_client = Mock()
        mock_sse_client.return_value = mock_client

        # First call raises error, second call raises KeyboardInterrupt to stop
        mock_process_events.side_effect = [
            requests.exceptions.ChunkedEncodingError(),
            KeyboardInterrupt(),
        ]

        routes = {"1"}

        try:
            client_thread(routes)
        except KeyboardInterrupt:
            pass

        # Verify connection was attempted multiple times
        assert mock_connect.call_count >= 2
