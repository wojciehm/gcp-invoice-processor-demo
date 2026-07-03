import unittest
from unittest.mock import patch, MagicMock
import sys
import os

# Add dashboard-worker to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'dashboard-worker')))

# Mock environment variables before importing
os.environ['BUCKET_PREFIX'] = 'test-prefix'

# Now we can safely import main without authenticating to GCP
with patch('google.auth.default', return_value=(MagicMock(), 'test-project')):
    with patch('google.cloud.storage.Client'):
        from main import handle_clear_data, storage_client, RAW_BUCKET_NAME, OS_BUCKET_NAME, GE_BUCKET_NAME

class TestDashboardWorker(unittest.TestCase):

    @patch('main.storage_client')
    @patch('main.set_status')
    def test_handle_clear_data(self, mock_set_status, mock_storage_client):
        # Setup mock buckets and blobs
        mock_bucket = MagicMock()
        mock_blob1 = MagicMock()
        mock_blob1.name = "invoice1.pdf"
        mock_blob2 = MagicMock()
        mock_blob2.name = "invoice2.pdf"
        
        mock_bucket.list_blobs.return_value = [mock_blob1, mock_blob2]
        mock_storage_client.bucket.return_value = mock_bucket
        
        # Execute
        handle_clear_data()
        
        # Assertions
        # It should process all 3 buckets
        self.assertEqual(mock_storage_client.bucket.call_count, 9)
        # Let's just check that blob.delete() was called
        # The worker fetches the bucket inside the lambda delete_blob_by_name
        # It does bucket = storage_client.bucket(bucket_name) for EACH blob.
        # 3 buckets * 1 call in outer loop + 3 buckets * 2 blobs in inner loop = 9 calls to bucket()
        
        self.assertTrue(mock_set_status.called)
        
        # Verify the exact buckets are accessed
        expected_buckets = [RAW_BUCKET_NAME, OS_BUCKET_NAME, GE_BUCKET_NAME]
        bucket_calls = [args[0][0] for args in mock_storage_client.bucket.call_args_list]
        for bucket in expected_buckets:
            self.assertIn(bucket, bucket_calls)

if __name__ == '__main__':
    unittest.main()
