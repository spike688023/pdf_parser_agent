import os
import time
import shutil
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

class SessionCleanup:
    """
    Background service to clean up expired sessions.
    Removes session directories and databases that have been inactive for too long.
    """
    
    def __init__(self, expiry_hours: int = 6):
        """
        Args:
            expiry_hours: Number of hours of inactivity before a session is considered expired
        """
        self.expiry_hours = expiry_hours
        self.expiry_seconds = expiry_hours * 3600
        
    def cleanup_expired_sessions(self):
        """
        Scan and delete all expired sessions.
        Cleans up both local files and GCS files.
        """
        try:
            current_time = time.time()
            cutoff_time = current_time - self.expiry_seconds
            
            # Track cleanup statistics
            deleted_count = 0
            freed_space = 0
            
            # Get list of expired sessions
            expired_sessions = set()
            
            # Clean up session directories in uploads/
            if os.path.exists("uploads"):
                for session_dir in os.listdir("uploads"):
                    session_path = os.path.join("uploads", session_dir)
                    if os.path.isdir(session_path):
                        if self._is_session_expired(session_dir, cutoff_time):
                            size = self._get_dir_size(session_path)
                            shutil.rmtree(session_path)
                            freed_space += size
                            deleted_count += 1
                            expired_sessions.add(session_dir)
                            logger.info(f"Deleted expired session directory: {session_dir}")
            
            # Clean up session databases in storage/
            if os.path.exists("storage"):
                for db_file in os.listdir("storage"):
                    if db_file.endswith("_metadata.db") or db_file.endswith("_faiss.index"):
                        session_id = db_file.split("_")[0]
                        if self._is_session_expired(session_id, cutoff_time):
                            db_path = os.path.join("storage", db_file)
                            if os.path.exists(db_path):
                                size = os.path.getsize(db_path)
                                os.remove(db_path)
                                freed_space += size
                                expired_sessions.add(session_id)
                                logger.info(f"Deleted expired session file: {db_file}")
            
            # Clean up GCS files for expired sessions
            if expired_sessions:
                try:
                    from src.gcs_storage import get_gcs_storage
                    gcs = get_gcs_storage()
                    
                    for session_id in expired_sessions:
                        # List and delete all files for this session
                        prefix = f"uploads/{session_id}/"
                        files = gcs.list_files(prefix=prefix)
                        
                        for file_path in files:
                            try:
                                gcs.delete_file(file_path)
                                logger.info(f"Deleted GCS file: {file_path}")
                            except Exception as e:
                                logger.warning(f"Failed to delete GCS file {file_path}: {e}")
                                
                except Exception as e:
                    logger.warning(f"Error cleaning up GCS files: {e}")
            
            if deleted_count > 0:
                logger.info(f"Cleanup complete: {deleted_count} sessions deleted, {freed_space / 1024 / 1024:.2f} MB freed")
            
            return deleted_count, freed_space
            
        except Exception as e:
            logger.error(f"Error during session cleanup: {e}")
            return 0, 0
    
    def _is_session_expired(self, session_id: str, cutoff_time: float) -> bool:
        """
        Check if a session has expired by querying its last activity time.
        """
        try:
            # Check session activity in the main activity tracker
            activity_db = "storage/session_activity.db"
            if not os.path.exists(activity_db):
                # If no activity tracker, check file modification time
                return self._check_file_mtime(session_id, cutoff_time)
            
            conn = sqlite3.connect(activity_db)
            cursor = conn.cursor()
            cursor.execute(
                "SELECT last_activity FROM session_activity WHERE session_id = ?",
                (session_id,)
            )
            result = cursor.fetchone()
            conn.close()
            
            if result:
                last_activity = result[0]
                return last_activity < cutoff_time
            else:
                # No record, check file modification time as fallback
                return self._check_file_mtime(session_id, cutoff_time)
                
        except Exception as e:
            logger.warning(f"Error checking session expiry for {session_id}: {e}")
            return False
    
    def _check_file_mtime(self, session_id: str, cutoff_time: float) -> bool:
        """
        Fallback: check file modification time if no activity record exists.
        """
        session_dir = f"uploads/{session_id}"
        if os.path.exists(session_dir):
            mtime = os.path.getmtime(session_dir)
            return mtime < cutoff_time
        return True  # If directory doesn't exist, consider it expired
    
    def _get_dir_size(self, path: str) -> int:
        """
        Calculate total size of a directory in bytes.
        """
        total = 0
        for dirpath, dirnames, filenames in os.walk(path):
            for filename in filenames:
                filepath = os.path.join(dirpath, filename)
                if os.path.exists(filepath):
                    total += os.path.getsize(filepath)
        return total

def update_session_activity(session_id: str):
    """
    Update the last activity timestamp for a session.
    Called on every user interaction.
    """
    try:
        os.makedirs("storage", exist_ok=True)
        activity_db = "storage/session_activity.db"
        
        conn = sqlite3.connect(activity_db)
        cursor = conn.cursor()
        
        # Create table if not exists
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS session_activity (
                session_id TEXT PRIMARY KEY,
                last_activity REAL,
                created_at REAL
            )
        """)
        
        current_time = time.time()
        
        # Insert or update
        cursor.execute("""
            INSERT INTO session_activity (session_id, last_activity, created_at)
            VALUES (?, ?, ?)
            ON CONFLICT(session_id) DO UPDATE SET last_activity = ?
        """, (session_id, current_time, current_time, current_time))
        
        conn.commit()
        conn.close()
        
    except Exception as e:
        logger.error(f"Error updating session activity: {e}")
