import copy
import csv
import io
import unittest
from unittest.mock import patch

import pandas as pd
from fastapi.testclient import TestClient
from backend import main


def fixture_payload(symbol="AAPL", selected_range="1Y"):
    return {"schema_version": 1, "symbol": symbol, "name": "Test fixture", "currency": "USD", "exchange": "TEST", "timezone": "America/New_York", "range": selected_range, "interval": "1d", "source": {"kind": "yahoo_yfinance", "label": "TEST FIXTURE", "simulated": False}, "fetched_at": "2025-01-05T12:00:00+00:00", "as_of": "2025-01-03T00:00:00-05:00", "quote": {"price": 110, "as_of": "2025-01-03T00:00:00-05:00", "kind": "last_returned_bar"}, "bars": [{"time": "2025-01-02T00:00:00-05:00", "open": 99, "high": 101, "low": 98, "close": 100, "adj_close": None, "volume": 1000, "dividends": 0, "stock_splits": 0}, {"time": "2025-01-03T00:00:00-05:00", "open": 100, "high": 112, "low": 99, "close": 110, "adj_close": 109, "volume": None, "dividends": 1, "stock_splits": 0}]}


class ApiTests(unittest.TestCase):
    def setUp(self):
        main.cache.clear()
        main.request_times.clear()
        self.client = TestClient(main.app)

    def test_health_does_not_claim_provider_availability(self):
        response = self.client.get('/api/health')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['provider'], 'yfinance')
        self.assertIn('does not guarantee', response.json()['notice'])

    def test_input_validation_does_not_call_provider(self):
        with patch.object(main, 'fetch_yahoo') as provider:
            self.assertEqual(self.client.get('/api/series', params={'symbol': '../../secret', 'range': '1Y'}).status_code, 422)
            self.assertEqual(self.client.get('/api/series', params={'symbol': 'AAPL', 'range': 'max'}).status_code, 422)
            provider.assert_not_called()

    def test_schema_and_cache_preserve_observation_time(self):
        with patch.object(main, 'fetch_yahoo', side_effect=fixture_payload) as provider:
            first = self.client.get('/api/series', params={'symbol': 'aapl', 'range': '1Y'})
            second = self.client.get('/api/series', params={'symbol': 'AAPL', 'range': '1Y'})
        self.assertEqual(first.status_code, 200)
        self.assertFalse(first.json()['cache']['hit'])
        self.assertTrue(second.json()['cache']['hit'])
        self.assertEqual(first.json()['fetched_at'], second.json()['fetched_at'])
        self.assertEqual(provider.call_count, 1)
        self.assertIsNone(second.json()['bars'][0]['adj_close'])
        self.assertEqual(second.headers['cache-control'], 'no-store')

    def test_failure_never_returns_simulated_quotes(self):
        with patch.object(main, 'fetch_yahoo', side_effect=RuntimeError('provider unavailable')) as provider:
            first = self.client.get('/api/series', params={'symbol': 'AAPL'})
            second = self.client.get('/api/series', params={'symbol': 'AAPL'})
        self.assertEqual(first.status_code, 503)
        self.assertEqual(second.status_code, 503)
        self.assertNotIn('bars', first.json())
        self.assertEqual(provider.call_count, 1)

    def test_csv_keeps_missing_values_and_provenance(self):
        with patch.object(main, 'fetch_yahoo', side_effect=fixture_payload):
            response = self.client.get('/api/download.csv', params={'symbol': 'AAPL', 'range': '1Y'})
        self.assertEqual(response.status_code, 200)
        records = list(csv.DictReader(io.StringIO(response.content.decode('utf-8-sig'))))
        self.assertEqual(len(records), 2)
        self.assertEqual(records[0]['Adj Close'], '')
        self.assertEqual(records[1]['Volume'], '')
        self.assertEqual(records[0]['Data Source'], 'TEST FIXTURE')
        self.assertEqual(records[0]['Fetched At'], '2025-01-05T12:00:00+00:00')

    def test_normalizer_keeps_close_and_adjusted_separate(self):
        frame = pd.DataFrame({'Open': [99, 100, 110], 'High': [101, 112, 113], 'Low': [98, 99, 109], 'Close': [100, 110, float('nan')], 'Adj Close': [98, float('nan'), 111], 'Volume': [1000, float('nan'), 1500]}, index=pd.date_range('2025-01-02', periods=3, tz='America/New_York'))
        bars = main.normalize_history(frame)
        self.assertEqual(len(bars), 2)
        self.assertEqual(bars[0]['close'], 100)
        self.assertEqual(bars[0]['adj_close'], 98)
        self.assertIsNone(bars[1]['adj_close'])
        self.assertIsNone(bars[1]['volume'])
        self.assertTrue(bars[0]['time'].endswith('-05:00'))

    def test_history_request_explicitly_disables_auto_adjust(self):
        frame = pd.DataFrame({'Open': [99, 100], 'High': [101, 112], 'Low': [98, 99], 'Close': [100, 110], 'Adj Close': [99, 109], 'Volume': [1000, 2000]}, index=pd.date_range('2025-01-02', periods=2, tz='America/New_York'))
        with patch.object(main.yf, 'Ticker') as factory:
            ticker = factory.return_value
            ticker.history.return_value = frame
            ticker.get_history_metadata.return_value = {'currency': 'USD', 'exchangeTimezoneName': 'America/New_York'}
            data = main.fetch_yahoo('AAPL', '1D')
            self.assertFalse(ticker.history.call_args.kwargs['auto_adjust'])
            self.assertEqual(ticker.history.call_args.kwargs['interval'], '1m')
            self.assertEqual(data['quote']['kind'], 'last_returned_bar')
            self.assertEqual(data['source']['kind'], 'yahoo_yfinance')

    def test_cors_read_only_without_credentials(self):
        response = self.client.get('/api/health', headers={'Origin': 'https://example.github.io'})
        self.assertEqual(response.headers['access-control-allow-origin'], '*')
        self.assertNotIn('access-control-allow-credentials', response.headers)

    def test_local_frontend_and_auto_configuration(self):
        self.assertEqual(self.client.get('/').status_code, 200)
        self.assertIn('window.location.origin', self.client.get('/config.js').text)

    def test_safe_csv_metadata(self):
        data = fixture_payload()
        data['source']['label'] = '=HYPERLINK("bad")'
        self.assertIn("'=HYPERLINK", main.to_csv(data))


if __name__ == '__main__':
    unittest.main()
