"""
Google Cloud Storage integration for PDF file management.
"""
import os
from typing import Optional, BinaryIO
from google.cloud import storage
from dotenv import load_dotenv
import logging

load_dotenv()

logger = logging.getLogger(__name__)


class GCSStorage:
    """Handles file operations with Google Cloud Storage."""
    
    def __init__(self, bucket_name: Optional[str] = None):
        """
        Initialize GCS client.
        
        Args:
            bucket_name: GCS bucket name. If None, reads from GCS_BUCKET_NAME env var.
        """
        self.bucket_name = bucket_name or os.getenv("GCS_BUCKET_NAME")
        if not self.bucket_name:
            raise ValueError("GCS_BUCKET_NAME must be set in environment or passed as argument")
        
        # Initialize GCS client
        # If GOOGLE_APPLICATION_CREDENTIALS is set, it will use that
        # Otherwise, it will use Application Default Credentials
        self.client = storage.Client()
        self.bucket = self.client.bucket(self.bucket_name)
        
        logger.info(f"Initialized GCS Storage with bucket: {self.bucket_name}")
    
    def upload_file(self, file_path: str, destination_blob_name: str) -> str:
        """
        Upload a file to GCS.
        
        Args:
            file_path: Local file path to upload
            destination_blob_name: Destination path in GCS bucket (e.g., "uploads/session_id/file.pdf")
        
        Returns:
            GCS URI (gs://bucket-name/path/to/file)
        """
        blob = self.bucket.blob(destination_blob_name)
        blob.upload_from_filename(file_path)
        
        gcs_uri = f"gs://{self.bucket_name}/{destination_blob_name}"
        logger.info(f"Uploaded {file_path} to {gcs_uri}")
        return gcs_uri
    
    def upload_from_file_object(self, file_obj: BinaryIO, destination_blob_name: str) -> str:
        """
        Upload from a file-like object (e.g., Streamlit UploadedFile).
        
        Args:
            file_obj: File-like object with read() method
            destination_blob_name: Destination path in GCS bucket
        
        Returns:
            GCS URI (gs://bucket-name/path/to/file)
        """
        blob = self.bucket.blob(destination_blob_name)
        file_obj.seek(0)  # Reset file pointer to beginning
        blob.upload_from_file(file_obj)
        
        gcs_uri = f"gs://{self.bucket_name}/{destination_blob_name}"
        logger.info(f"Uploaded file object to {gcs_uri}")
        return gcs_uri
    
    def download_file(self, blob_name: str, destination_path: str) -> str:
        """
        Download a file from GCS to local path.
        
        Args:
            blob_name: Path in GCS bucket
            destination_path: Local path to save file
        
        Returns:
            Local file path
        """
        blob = self.bucket.blob(blob_name)
        
        # Create directory if it doesn't exist
        os.makedirs(os.path.dirname(destination_path), exist_ok=True)
        
        blob.download_to_filename(destination_path)
        logger.info(f"Downloaded gs://{self.bucket_name}/{blob_name} to {destination_path}")
        return destination_path
    
    def download_to_temp(self, blob_name: str) -> str:
        """
        Download a file from GCS to a temporary location.
        
        Args:
            blob_name: Path in GCS bucket
        
        Returns:
            Temporary file path
        """
        import tempfile
        
        # Get file extension from blob name
        _, ext = os.path.splitext(blob_name)
        
        # Create temp file
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=ext)
        temp_path = temp_file.name
        temp_file.close()
        
        return self.download_file(blob_name, temp_path)
    
    def delete_file(self, blob_name: str) -> bool:
        """
        Delete a file from GCS.
        
        Args:
            blob_name: Path in GCS bucket
        
        Returns:
            True if deleted successfully
        """
        blob = self.bucket.blob(blob_name)
        blob.delete()
        logger.info(f"Deleted gs://{self.bucket_name}/{blob_name}")
        return True
    
    def list_files(self, prefix: str = "") -> list[str]:
        """
        List files in GCS bucket with optional prefix.
        
        Args:
            prefix: Filter files by prefix (e.g., "uploads/session_id/")
        
        Returns:
            List of blob names
        """
        blobs = self.client.list_blobs(self.bucket_name, prefix=prefix)
        return [blob.name for blob in blobs]
    
    def file_exists(self, blob_name: str) -> bool:
        """
        Check if a file exists in GCS.
        
        Args:
            blob_name: Path in GCS bucket
        
        Returns:
            True if file exists
        """
        blob = self.bucket.blob(blob_name)
        return blob.exists()
    
    def get_public_url(self, blob_name: str) -> str:
        """
        Get public URL for a blob (if bucket is public).
        
        Args:
            blob_name: Path in GCS bucket
        
        Returns:
            Public URL
        """
        return f"https://storage.googleapis.com/{self.bucket_name}/{blob_name}"
    
    def get_signed_url(self, blob_name: str, expiration_minutes: int = 60) -> str:
        """
        Generate a signed URL for temporary access to a private file.
        
        Args:
            blob_name: Path in GCS bucket
            expiration_minutes: URL expiration time in minutes
        
        Returns:
            Signed URL
        """
        from datetime import timedelta
        
        blob = self.bucket.blob(blob_name)
        url = blob.generate_signed_url(
            version="v4",
            expiration=timedelta(minutes=expiration_minutes),
            method="GET"
        )
        return url


# Singleton instance for easy import
_gcs_storage_instance: Optional[GCSStorage] = None


def get_gcs_storage() -> GCSStorage:
    """Get or create GCS storage singleton instance."""
    global _gcs_storage_instance
    if _gcs_storage_instance is None:
        _gcs_storage_instance = GCSStorage()
    return _gcs_storage_instance
