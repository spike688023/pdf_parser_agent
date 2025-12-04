"""
Unit tests for Firestore integration.
Uses mocking to avoid actual Firestore calls.
"""
import unittest
from unittest.mock import MagicMock, patch
import sys
import os

# Add src to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.firestore_db import FirestoreDB

class TestFirestoreDB(unittest.TestCase):
    
    @patch('src.firestore_db.firestore.Client')
    def setUp(self, mock_client_class):
        self.mock_client = MagicMock()
        mock_client_class.return_value = self.mock_client
        
        self.project_id = "test-project"
        self.session_id = "test-session"
        
        self.db = FirestoreDB(
            project_id=self.project_id,
            session_id=self.session_id
        )

    def test_init(self):
        """Test initialization"""
        self.assertEqual(self.db.project_id, self.project_id)
        self.assertEqual(self.db.session_id, self.session_id)

    def test_save_document_metadata(self):
        """Test saving document metadata"""
        mock_doc_ref = MagicMock()
        self.mock_client.collection.return_value.document.return_value\
                       .collection.return_value.document.return_value = mock_doc_ref
        
        self.db.save_document_metadata(
            document_id="doc1",
            document_name="Test Doc",
            file_path="gs://bucket/file.pdf",
            tags="test",
            highlights="highlight",
            chunk_count=10
        )
        
        mock_doc_ref.set.assert_called_once()
        call_args = mock_doc_ref.set.call_args[0][0]
        self.assertEqual(call_args["document_id"], "doc1")
        self.assertEqual(call_args["document_name"], "Test Doc")

    def test_get_document_metadata(self):
        """Test retrieving document metadata"""
        mock_doc = MagicMock()
        mock_doc.exists = True
        mock_doc.to_dict.return_value = {
            "document_id": "doc1",
            "document_name": "Test Doc"
        }
        
        self.mock_client.collection.return_value.document.return_value\
                       .collection.return_value.document.return_value.get.return_value = mock_doc
        
        result = self.db.get_document_metadata("doc1")
        
        self.assertIsNotNone(result)
        self.assertEqual(result["document_id"], "doc1")

    def test_add_chunks(self):
        """Test adding chunks"""
        items = [
            {"text": "chunk1", "page_number": 1, "source": "test.pdf", "document_id": "doc1"},
            {"text": "chunk2", "page_number": 2, "source": "test.pdf", "document_id": "doc1"}
        ]
        
        mock_collection = MagicMock()
        self.mock_client.collection.return_value.document.return_value\
                       .collection.return_value = mock_collection
        
        # Mock document references
        mock_doc_ref1 = MagicMock()
        mock_doc_ref1.id = "chunk_id_1"
        mock_doc_ref2 = MagicMock()
        mock_doc_ref2.id = "chunk_id_2"
        
        mock_collection.document.side_effect = [mock_doc_ref1, mock_doc_ref2]
        
        mock_batch = MagicMock()
        self.mock_client.batch.return_value = mock_batch
        
        ids = self.db.add_chunks(items)
        
        self.assertEqual(len(ids), 2)
        self.assertEqual(ids[0], "chunk_id_1")
        self.assertEqual(ids[1], "chunk_id_2")
        mock_batch.commit.assert_called_once()

if __name__ == '__main__':
    unittest.main()
