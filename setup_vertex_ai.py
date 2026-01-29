"""
Helper script to setup Vertex AI Vector Search resources.
"""
import os
import time
from google.cloud import aiplatform
from dotenv import load_dotenv

load_dotenv()

def setup_vertex_resources():
    print("🚀 Starting Vertex AI Vector Search Setup")
    print("========================================")
    
    # Configuration
    project_id = os.getenv("GOOGLE_CLOUD_PROJECT")
    location = os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1")
    bucket_name = os.getenv("GCS_BUCKET_NAME")
    
    if not project_id:
        print("❌ Error: GOOGLE_CLOUD_PROJECT not set in .env")
        return
    
    print(f"Project: {project_id}")
    print(f"Location: {location}")
    print(f"Bucket: {bucket_name}")
    print("----------------------------------------")
    
    try:
        aiplatform.init(project=project_id, location=location)
        
        # 1. Create Index
        index_display_name = "pdf_agent_vector_index"
        print(f"\n1️⃣  Creating Vector Search Index: {index_display_name}")
        print("   (This typically takes 30-60 minutes...)")
        
        # Check if index already exists
        indexes = aiplatform.MatchingEngineIndex.list(filter=f'display_name="{index_display_name}"')
        if indexes:
            my_index = indexes[0]
            print(f"   ✅ Index already exists: {my_index.resource_name}")
        else:
            # Create new index
            # Note: We use a dummy embedding to initialize the index structure
            # Dimensions: 1024 (matching nvidia/llama-3.2-nv-embedqa-1b-v2)
            # Distance measure: DOT_PRODUCT_DISTANCE (recommended for embeddings)
            # Algorithm: TREE_AH_ALGORITHM (standard for ANN)
            bucket_uri = f"gs://{bucket_name}/matching_engine_index_data"
            my_index = aiplatform.MatchingEngineIndex.create_tree_ah_index(
                display_name=index_display_name,
                contents_delta_uri=bucket_uri,
                dimensions=1024,
                distance_measure_type="DOT_PRODUCT_DISTANCE",
                description="Index for PDF Agent",
                index_update_method="STREAM_UPDATE"
            )
            print(f"   ✅ Index created: {my_index.resource_name}")

        # 2. Create Endpoint
        endpoint_display_name = "pdf_agent_endpoint"
        print(f"\n2️⃣  Creating Index Endpoint: {endpoint_display_name}")
        print("   (This takes a few minutes...)")
        
        endpoints = aiplatform.MatchingEngineIndexEndpoint.list(filter=f'display_name="{endpoint_display_name}"')
        if endpoints:
            my_endpoint = endpoints[0]
            print(f"   ✅ Endpoint already exists: {my_endpoint.resource_name}")
        else:
            my_endpoint = aiplatform.MatchingEngineIndexEndpoint.create(
                display_name=endpoint_display_name,
                description="Endpoint for PDF Agent",
                public_endpoint_enabled=True
            )
            print(f"   ✅ Endpoint created: {my_endpoint.resource_name}")

        # 3. Deploy Index
        deployed_index_id = "pdf_agent_deployed_index"
        print(f"\n3️⃣  Deploying Index to Endpoint")
        print("   (This typically takes 20-30 minutes...)")
        
        # Check if already deployed
        is_deployed = False
        for deployed_index in my_endpoint.deployed_indexes:
            if deployed_index.id == deployed_index_id:
                is_deployed = True
                break
        
        if is_deployed:
            print(f"   ✅ Index already deployed: {deployed_index_id}")
        else:
            my_endpoint.deploy_index(
                index=my_index,
                deployed_index_id=deployed_index_id,
                display_name=deployed_index_id,
                machine_type="e2-standard-2",  # Cost-effective option
                min_replica_count=1,
                max_replica_count=1
            )
            print(f"   ✅ Index deployed successfully")

        print("\n🎉 Setup Complete!")
        print("========================================")
        print("Please update your .env file with the following:")
        print(f"VERTEX_INDEX_ENDPOINT_NAME={my_endpoint.resource_name}")
        print(f"VERTEX_DEPLOYED_INDEX_ID={deployed_index_id}")
        
    except Exception as e:
        print(f"\n❌ Error during setup: {e}")

if __name__ == "__main__":
    setup_vertex_resources()
