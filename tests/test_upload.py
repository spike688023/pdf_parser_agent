"""
Interactive script to test uploading files to GCS.

python test_upload.py /Users/linspike/Documents/sample.pdf

"""
import sys
import os
from src.gcs_storage import get_gcs_storage


def test_upload(file_path: str):
    """Test uploading a file to GCS."""
    
    # Check if file exists
    if not os.path.exists(file_path):
        print(f"❌ Error: File not found: {file_path}")
        return False
    
    # Get file info
    file_name = os.path.basename(file_path)
    file_size = os.path.getsize(file_path)
    
    print(f"📄 File: {file_name}")
    print(f"📊 Size: {file_size:,} bytes ({file_size / 1024:.2f} KB)")
    print()
    
    # Upload to GCS
    try:
        gcs = get_gcs_storage()
        
        # Use a test path in GCS
        destination_blob_name = f"test_uploads/{file_name}"
        
        print(f"⬆️  Uploading to GCS...")
        print(f"   Destination: gs://{gcs.bucket_name}/{destination_blob_name}")
        
        gcs_uri = gcs.upload_file(
            file_path=file_path,
            destination_blob_name=destination_blob_name
        )
        
        print(f"\n✅ Upload successful!")
        print(f"   GCS URI: {gcs_uri}")
        
        # Verify the file exists
        if gcs.file_exists(destination_blob_name):
            print(f"   ✓ File verified in bucket")
        
        # Get public URL (won't work if bucket is private, but shows the URL format)
        public_url = gcs.get_public_url(destination_blob_name)
        print(f"   Public URL: {public_url}")
        
        return True
        
    except Exception as e:
        print(f"\n❌ Upload failed:")
        print(f"   {type(e).__name__}: {e}")
        return False


def main():
    """Main function."""
    print("🧪 GCS Upload Test\n")
    
    # Check if file path provided as argument
    if len(sys.argv) > 1:
        file_path = sys.argv[1]
    else:
        # Interactive mode
        print("Enter the path to the file you want to upload:")
        print("(or press Ctrl+C to cancel)")
        file_path = input("File path: ").strip()
    
    # Remove quotes if user copy-pasted a path with quotes
    file_path = file_path.strip('"').strip("'")
    
    print()
    success = test_upload(file_path)
    
    if success:
        print("\n🎉 Test completed successfully!")
    else:
        print("\n❌ Test failed. Please check the error message above.")
    
    return 0 if success else 1


if __name__ == "__main__":
    try:
        exit(main())
    except KeyboardInterrupt:
        print("\n\n⚠️  Test cancelled by user.")
        exit(1)
