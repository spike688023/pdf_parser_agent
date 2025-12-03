"""
Script to delete files from GCS bucket.

使用方式 (Usage):
===============

1. 列出所有檔案 (List all files):
   python tests/delete_from_gcs.py list

2. 刪除特定檔案 (Delete specific file):
   python tests/delete_from_gcs.py delete uploads/session_123/file.pdf

3. 刪除整個 session 的所有檔案 (Delete all files for a session):
   python tests/delete_from_gcs.py session abc123-def456


其他刪除方式 (Alternative Methods):
===================================

方法 1: 透過 Streamlit UI 刪除（推薦）
   1. 打開 http://localhost:8501
   2. 在左側邊欄找到你上傳的文件
   3. 展開文件資訊
   4. 點擊 🗑️ Delete 按鈕
   → 系統會自動從資料庫和 GCS 刪除

方法 2: 使用 GCS Console（網頁介面）
   1. 前往 https://console.cloud.google.com/storage/browser
   2. 選擇 bucket: my-pdf-files__spike688023
   3. 瀏覽到要刪除的檔案
   4. 勾選檔案
   5. 點擊 Delete 按鈕

方法 3: 使用 gsutil 命令（需要安裝 gcloud SDK）
   # 刪除單一檔案
   gsutil rm gs://my-pdf-files__spike688023/uploads/session_id/file.pdf
   
   # 刪除整個資料夾
   gsutil -m rm -r gs://my-pdf-files__spike688023/uploads/session_id/
   
   # 列出所有檔案
   gsutil ls gs://my-pdf-files__spike688023/

方法 4: 使用 Python 程式碼
   from src.gcs_storage import get_gcs_storage
   
   gcs = get_gcs_storage()
   gcs.delete_file("uploads/session_id/file.pdf")

"""
import sys
from src.gcs_storage import get_gcs_storage


def delete_file(blob_name: str):
    """Delete a specific file from GCS."""
    try:
        gcs = get_gcs_storage()
        
        print(f"🗑️  Deleting: gs://{gcs.bucket_name}/{blob_name}")
        
        # Check if file exists
        if not gcs.file_exists(blob_name):
            print(f"❌ File not found: {blob_name}")
            return False
        
        # Delete the file
        gcs.delete_file(blob_name)
        print(f"✅ Successfully deleted!")
        
        return True
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return False


def list_and_delete_session(session_id: str):
    """List and delete all files for a specific session."""
    try:
        gcs = get_gcs_storage()
        
        # List files for this session
        prefix = f"uploads/{session_id}/"
        files = gcs.list_files(prefix=prefix)
        
        if not files:
            print(f"📁 No files found for session: {session_id}")
            return
        
        print(f"📁 Found {len(files)} file(s) for session {session_id}:")
        for i, file_path in enumerate(files, 1):
            print(f"   {i}. {file_path}")
        
        # Confirm deletion
        response = input(f"\n⚠️  Delete all {len(files)} file(s)? (yes/no): ")
        
        if response.lower() in ['yes', 'y']:
            deleted = 0
            for file_path in files:
                try:
                    gcs.delete_file(file_path)
                    print(f"   ✅ Deleted: {file_path}")
                    deleted += 1
                except Exception as e:
                    print(f"   ❌ Failed to delete {file_path}: {e}")
            
            print(f"\n🎉 Deleted {deleted}/{len(files)} file(s)")
        else:
            print("❌ Deletion cancelled")
        
    except Exception as e:
        print(f"❌ Error: {e}")


def list_all_files():
    """List all files in the bucket."""
    try:
        gcs = get_gcs_storage()
        
        print(f"📁 Listing all files in bucket: {gcs.bucket_name}\n")
        
        files = gcs.list_files()
        
        if not files:
            print("   Bucket is empty")
            return
        
        print(f"Found {len(files)} file(s):\n")
        for i, file_path in enumerate(files, 1):
            print(f"{i}. {file_path}")
        
    except Exception as e:
        print(f"❌ Error: {e}")


def main():
    """Main function."""
    print("🗑️  GCS File Deletion Tool\n")
    
    if len(sys.argv) < 2:
        print("Usage:")
        print("  1. Delete specific file:")
        print("     python delete_from_gcs.py delete <blob_name>")
        print("     Example: python delete_from_gcs.py delete uploads/session_123/file.pdf")
        print()
        print("  2. Delete all files for a session:")
        print("     python delete_from_gcs.py session <session_id>")
        print("     Example: python delete_from_gcs.py session abc123-def456")
        print()
        print("  3. List all files:")
        print("     python delete_from_gcs.py list")
        return
    
    command = sys.argv[1].lower()
    
    if command == "list":
        list_all_files()
    
    elif command == "delete" and len(sys.argv) >= 3:
        blob_name = sys.argv[2]
        delete_file(blob_name)
    
    elif command == "session" and len(sys.argv) >= 3:
        session_id = sys.argv[2]
        list_and_delete_session(session_id)
    
    else:
        print("❌ Invalid command. Use 'list', 'delete', or 'session'")


if __name__ == "__main__":
    main()
