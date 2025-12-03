"""
Test script to verify Google Cloud Storage connection.
"""
from src.gcs_storage import get_gcs_storage
import os
from dotenv import load_dotenv

load_dotenv()


def test_gcs_connection():
    """Test GCS connection and basic operations."""
    print("🔍 Testing Google Cloud Storage connection...\n")
    
    # Check environment variables
    print("📋 Environment Variables:")
    bucket_name = os.getenv("GCS_BUCKET_NAME")
    credentials_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
    project_id = os.getenv("GOOGLE_CLOUD_PROJECT")
    
    print(f"  - GCS_BUCKET_NAME: {bucket_name}")
    print(f"  - GOOGLE_APPLICATION_CREDENTIALS: {credentials_path}")
    print(f"  - GOOGLE_CLOUD_PROJECT: {project_id}")
    print()
    
    if not bucket_name:
        print("❌ Error: GCS_BUCKET_NAME not set in .env file")
        return False
    
    if credentials_path and not os.path.exists(credentials_path):
        print(f"❌ Error: Credentials file not found at {credentials_path}")
        return False
    
    # Test connection
    try:
        gcs = get_gcs_storage()
        print(f"✅ Successfully connected to bucket: {gcs.bucket_name}\n")
        
        # List files in bucket
        print("📁 Listing files in bucket...")
        files = gcs.list_files()
        
        if files:
            print(f"   Found {len(files)} file(s):")
            for i, file in enumerate(files[:10], 1):  # Show first 10 files
                print(f"   {i}. {file}")
            if len(files) > 10:
                print(f"   ... and {len(files) - 10} more files")
        else:
            print("   Bucket is empty (this is normal for a new bucket)")
        
        print("\n✅ All tests passed! GCS is configured correctly.")
        return True
        
    except Exception as e:
        print(f"\n❌ Error connecting to GCS:")
        print(f"   {type(e).__name__}: {e}")
        print("\n💡 Troubleshooting tips:")
        print("   1. Make sure you've created a .env file (copy from .env.example)")
        print("   2. Verify your Service Account JSON key path is correct")
        print("   3. Check that the Service Account has 'Storage Object Admin' role")
        print("   4. Confirm the bucket name is correct")
        print("\n   See GCS_SETUP.md for detailed setup instructions.")
        return False


if __name__ == "__main__":
    success = test_gcs_connection()
    exit(0 if success else 1)
