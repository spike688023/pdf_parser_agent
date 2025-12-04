"""
Vertex AI Vector Search integration.
"""
import os
import logging
from typing import List, Dict, Any, Optional
import numpy as np
from google.cloud import aiplatform
from google.protobuf import struct_pb2

logger = logging.getLogger(__name__)

class VertexVectorStore:
    """
    Client for Vertex AI Vector Search.
    """
    
    def __init__(self, 
                 project_id: str, 
                 location: str, 
                 index_endpoint_name: str, 
                 deployed_index_id: str,
                 api_endpoint: Optional[str] = None):
        """
        Initialize Vertex AI Vector Search client.
        
        Args:
            project_id: GCP Project ID
            location: GCP Region (e.g., us-central1)
            index_endpoint_name: Full resource name of the Index Endpoint
                                 (projects/.../locations/.../indexEndpoints/...)
            deployed_index_id: ID of the deployed index
            api_endpoint: Optional custom API endpoint
        """
        self.project_id = project_id
        self.location = location
        self.index_endpoint_name = index_endpoint_name
        self.deployed_index_id = deployed_index_id
        
        # Initialize Vertex AI SDK
        aiplatform.init(project=project_id, location=location)
        
        # Create IndexEndpoint client
        self.index_endpoint = aiplatform.MatchingEngineIndexEndpoint(
            index_endpoint_name=index_endpoint_name
        )
        
        logger.info(f"Initialized Vertex AI Vector Search: {index_endpoint_name} (Index: {deployed_index_id})")

    def search(self, query_embedding: np.ndarray, k: int = 5) -> List[Dict[str, Any]]:
        """
        Search for nearest neighbors in Vertex AI Vector Search.
        
        Args:
            query_embedding: Query vector (numpy array)
            k: Number of neighbors to return
            
        Returns:
            List of results with 'id' and 'distance'
        """
        try:
            # Ensure embedding is a list of floats
            if isinstance(query_embedding, np.ndarray):
                query_vector = query_embedding.tolist()
            else:
                query_vector = query_embedding
                
            # If it's a 2D array (1, dim), flatten it
            if isinstance(query_vector[0], list):
                query_vector = query_vector[0]
                
            # Perform search
            response = self.index_endpoint.find_neighbors(
                deployed_index_id=self.deployed_index_id,
                queries=[query_vector],
                num_neighbors=k
            )
            
            # Parse results
            results = []
            if response:
                for neighbor in response[0]:
                    results.append({
                        "id": neighbor.id,
                        "distance": neighbor.distance
                    })
            
            return results
            
        except Exception as e:
            logger.error(f"Error querying Vertex AI Vector Search: {e}")
            raise

    def add_items(self, ids: List[str], embeddings: np.ndarray):
        """
        Add items to the index using Streaming Update.
        
        Args:
            ids: List of unique IDs for the items
            embeddings: Numpy array of embeddings
        """
        try:
            from google.cloud import aiplatform_v1
            
            # Convert to list of Datapoints
            datapoints = []
            for i, doc_id in enumerate(ids):
                # Ensure embedding is a list of floats
                embedding_vector = embeddings[i].tolist()
                
                datapoint = aiplatform_v1.IndexDatapoint(
                    datapoint_id=str(doc_id),
                    feature_vector=embedding_vector
                )
                datapoints.append(datapoint)
            
            # Upsert to Index
            # Note: This requires the index to be created with index_update_method="STREAM_UPDATE"
            # If standard index, this might fail or be slow.
            # For standard index, we should use `index.upsert_datapoints` (not endpoint)
            # But the SDK structure is a bit complex.
            # Let's try to get the Index resource and upsert there.
            
            # Get the index resource
            # We need the index resource name. 
            # For simplicity, we assume the user provided deployed_index_id, 
            # but we need the actual Index ID to upsert.
            # Let's try to find it from the endpoint.
            
            my_index_id = None
            for deployed in self.index_endpoint.deployed_indexes:
                if deployed.id == self.deployed_index_id:
                    my_index_id = deployed.index
                    break
            
            if not my_index_id:
                logger.warning(f"Could not find deployed index {self.deployed_index_id} in endpoint")
                return

            # Initialize Index client
            my_index = aiplatform.MatchingEngineIndex(index_name=my_index_id)
            
            # Upsert
            my_index.upsert_datapoints(datapoints=datapoints)
            logger.info(f"Successfully upserted {len(datapoints)} items to Vertex AI")
            
        except Exception as e:
            logger.error(f"Error upserting to Vertex AI: {e}")
            # Don't raise, just log, so we don't break the local flow
            logger.warning("Streaming update failed. This might be because the Index is not configured for streaming.")
