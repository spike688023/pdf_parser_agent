"""
Unit tests for Vertex AI Vector Search integration.
Uses mocking to avoid actual API calls.
"""
import unittest
from unittest.mock import MagicMock, patch
import numpy as np
import sys
import os

# Add src to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.vertex_search import VertexVectorStore

class TestVertexVectorStore(unittest.TestCase):
    
    @patch('src.vertex_search.aiplatform')
    def setUp(self, mock_aiplatform):
        self.mock_aiplatform = mock_aiplatform
        self.project_id = "test-project"
        self.location = "us-east1"
        self.index_endpoint_name = "projects/p/locations/l/indexEndpoints/ie"
        self.deployed_index_id = "test_index"
        
        # Mock IndexEndpoint
        self.mock_endpoint = MagicMock()
        self.mock_aiplatform.MatchingEngineIndexEndpoint.return_value = self.mock_endpoint
        
        self.store = VertexVectorStore(
            project_id=self.project_id,
            location=self.location,
            index_endpoint_name=self.index_endpoint_name,
            deployed_index_id=self.deployed_index_id
        )

    def test_init(self):
        """Test initialization"""
        self.mock_aiplatform.init.assert_called_with(project=self.project_id, location=self.location)
        self.mock_aiplatform.MatchingEngineIndexEndpoint.assert_called_with(index_endpoint_name=self.index_endpoint_name)

    def test_search(self):
        """Test search functionality"""
        # Mock response
        mock_neighbor = MagicMock()
        mock_neighbor.id = "1"
        mock_neighbor.distance = 0.9
        self.mock_endpoint.find_neighbors.return_value = [[mock_neighbor]]
        
        query = np.array([0.1, 0.2, 0.3])
        results = self.store.search(query, k=2)
        
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]['id'], "1")
        self.assertEqual(results[0]['distance'], 0.9)
        
        # Verify call
        self.mock_endpoint.find_neighbors.assert_called_once()
        call_args = self.mock_endpoint.find_neighbors.call_args
        self.assertEqual(call_args.kwargs['deployed_index_id'], self.deployed_index_id)
        self.assertEqual(call_args.kwargs['num_neighbors'], 2)

    @patch('src.vertex_search.aiplatform.MatchingEngineIndex')
    def test_add_items(self, mock_index_cls):
        """Test add_items (upsert)"""
        # Mock deployed index finding
        mock_deployed = MagicMock()
        mock_deployed.id = self.deployed_index_id
        mock_deployed.index = "projects/p/locations/l/indexes/i"
        self.mock_endpoint.deployed_indexes = [mock_deployed]
        
        # Mock Index client
        mock_index_client = MagicMock()
        mock_index_cls.return_value = mock_index_client
        
        ids = ["1", "2"]
        embeddings = np.array([[0.1, 0.2], [0.3, 0.4]])
        
        # We need to mock aiplatform_v1 inside the method or globally
        with patch('google.cloud.aiplatform_v1.IndexDatapoint') as mock_datapoint:
            self.store.add_items(ids, embeddings)
            
            # Verify upsert called
            mock_index_client.upsert_datapoints.assert_called_once()
            self.assertEqual(len(mock_index_client.upsert_datapoints.call_args.kwargs['datapoints']), 2)

if __name__ == '__main__':
    unittest.main()
