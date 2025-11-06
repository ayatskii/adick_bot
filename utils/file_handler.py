import os
import logging
import tempfile
import shutil
import time
import hashlib
from pathlib import Path
from typing import Dict, List, Optional, Union
from app.config import settings

# Get logger for this module
logger = logging.getLogger(__name__)

class FileHandler:
    def __init__(self):
        self.upload_dir = Path(settings.upload_dir)

        self.upload_dir.mkdir(exist_ok=True, parents=True)

        logger.info(f"File directory initialized in directory {self.upload_dir.absolute()}")

        self._created_files_ = list()

    def create_temp_file(self, suffix: str = ".tmp", prefix:str = "audio_") -> str:
        try:
            temp_file = tempfile.NamedTemporaryFile(
                delete=False,
                suffix=suffix,
                prefix=prefix,
                dir=self.upload_dir
            )

            temp_file_path = temp_file.name

            logger.debug("Created temporary file {temp_File_path}")

            return temp_file_path
        except Exception as e:
            logger.error(f"Failed to create temporary file: {e}")
            raise OSError(f"Could not create temporary file: {e}")
        
    def cleanup_file(self, file_path: Union[str, Path]) -> bool:
        try:
            path = Path(file_path)
            
            if path.exists() and path.is_file():
                path.unlink()

                if str(file_path) in self._created_files_:
                    self._created_files_.remove(str(file_path))

                logger.debug("File succesfully deleted {file_path}")
                return True
            else:
                logger.warning("File not found for deletion")
                return False
        except PermissionError as e:
            logger.error("Permission denied {e}")
            return False
        except Exception as e:
            logger.error("Error occured while fle deletion {e}")    
            return False
        
    def get_file_info(self, file_path: Union[str, Path]) -> Dict[str, Union[int, float, str]]:
        """
        Get comprehensive information about a file
        
        Args:
            file_path: Path to the file
            
        Returns:
            dict: File information including size, timestamps, extension, etc.
            
        Example:
            info = handler.get_file_info("audio.wav")
            print(f"File size: {info['size']} bytes")
        """
        try:
            path = Path(file_path)
            
            if not path.exists():
                logger.warning(f"File does not exist: {file_path}")
                return {}
            
            stat_info = path.stat()
            
            file_hash = self._calculate_file_hash(path)
            
            file_info = {
                "path": str(path.absolute()),
                "name": path.name,
                "extension": path.suffix.lower(),
                "size": stat_info.st_size,
                "size_mb": round(stat_info.st_size / (1024 * 1024), 2),
                "created": stat_info.st_ctime,
                "modified": stat_info.st_mtime,
                "accessed": stat_info.st_atime,
                "is_readable": os.access(path, os.R_OK),
                "is_writable": os.access(path, os.W_OK),
                "md5_hash": file_hash,
            }
            
            logger.debug(f"Retrieved file info for: {file_path}")
            return file_info
            
        except Exception as e:
            logger.error(f"Error getting file info for {file_path}: {e}")
            return {"error": str(e)}

    def validate_audio_file(self, file_path: Union[str, Path]) -> Dict[str, Union[bool, str]]:
        """
        Validate an audio file for processing
        
        Args:
            file_path: Path to the audio file
            
        Returns:
            dict: Validation results with success status and error message if any
            
        Example:
            result = handler.validate_audio_file("audio.mp3")
            if result["valid"]:
                print("File is valid for processing")
        """
        try:
            path = Path(file_path)
            
            # Check if file exists
            if not path.exists():
                return {"valid": False, "error": "File does not exist"}
            
            # Get file info
            file_info = self.get_file_info(path)
            
            if not file_info or "error" in file_info:
                return {"valid": False, "error": "Could not read file information"}
            
            # Check file size
            if file_info["size"] > settings.max_file_size:
                max_mb = settings.max_file_size / (1024 * 1024)
                return {
                    "valid": False, 
                    "error": f"File too large: {file_info['size_mb']}MB > {max_mb}MB"
                }
            
            # Check if file is empty
            if file_info["size"] == 0:
                return {"valid": False, "error": "File is empty"}
            
            # Check file extension
            valid_extensions = {".mp3", ".wav", ".ogg", ".m4a", ".flac", ".aac"}
            if file_info["extension"] not in valid_extensions:
                return {
                    "valid": False, 
                    "error": f"Unsupported file type: {file_info['extension']}"
                }
            
            # All checks passed
            return {
                "valid": True, 
                "size_mb": file_info["size_mb"],
                "extension": file_info["extension"]
            }
            
        except Exception as e:
            logger.error(f"Error validating file {file_path}: {e}")
            return {"valid": False, "error": str(e)}
    
    def cleanup_old_files(self, max_age_hours: int = 24) -> int:
        """
        Clean up old temporary files from the upload directory
        
        Args:
            max_age_hours: Maximum age of files to keep (in hours)
            
        Returns:
            int: Number of files cleaned up
            
        This method should be called periodically to prevent disk space issues.
        """
        try:
            current_time = time.time()
            max_age_seconds = max_age_hours * 3600
            cleaned_count = 0
            
            logger.info(f"Starting cleanup of files older than {max_age_hours} hours")
            
            # Iterate through all files in upload directory
            for file_path in self.upload_dir.iterdir():
                if file_path.is_file():
                    try:
                        # Calculate file age
                        file_age = current_time - file_path.stat().st_mtime
                        
                        if file_age > max_age_seconds:
                            # File is too old, delete it
                            file_path.unlink()
                            cleaned_count += 1
                            logger.debug(f"Cleaned up old file: {file_path.name}")
                            
                    except Exception as e:
                        logger.warning(f"Could not clean up file {file_path}: {e}")
            
            if cleaned_count > 0:
                logger.info(f"Cleaned up {cleaned_count} old files")
            else:
                logger.debug("No old files found to clean up")
            
            return cleaned_count
            
        except Exception as e:
            logger.error(f"Error during file cleanup: {e}")
            return 0
    
    def get_directory_stats(self) -> Dict[str, Union[int, float]]:
        """
        Get statistics about the upload directory
        
        Returns:
            dict: Directory statistics including file count, total size, etc.
        """
        try:
            file_count = 0
            total_size = 0
            oldest_file = None
            newest_file = None
            
            for file_path in self.upload_dir.iterdir():
                if file_path.is_file():
                    file_count += 1
                    file_size = file_path.stat().st_size
                    total_size += file_size
                    
                    file_mtime = file_path.stat().st_mtime
                    if oldest_file is None or file_mtime < oldest_file:
                        oldest_file = file_mtime
                    if newest_file is None or file_mtime > newest_file:
                        newest_file = file_mtime
            
            return {
                "file_count": file_count,
                "total_size_bytes": total_size,
                "total_size_mb": round(total_size / (1024 * 1024), 2),
                "oldest_file_age_hours": (time.time() - oldest_file) / 3600 if oldest_file else 0,
                "newest_file_age_hours": (time.time() - newest_file) / 3600 if newest_file else 0,
                "directory_path": str(self.upload_dir.absolute())
            }
            
        except Exception as e:
            logger.error(f"Error getting directory stats: {e}")
            return {"error": str(e)}
    
    def _calculate_file_hash(self, file_path: Path, chunk_size: int = 8192) -> str:
        """
        Calculate MD5 hash of a file for integrity checking
        
        Args:
            file_path: Path to the file
            chunk_size: Size of chunks to read at a time
            
        Returns:
            str: MD5 hash of the file
        """
        try:
            hash_md5 = hashlib.md5()
            
            with open(file_path, "rb") as f:
                # Read file in chunks to handle large files efficiently
                for chunk in iter(lambda: f.read(chunk_size), b""):
                    hash_md5.update(chunk)
            
            return hash_md5.hexdigest()
            
        except Exception as e:
            logger.warning(f"Could not calculate hash for {file_path}: {e}")
            return "unknown"
    
    def __del__(self):
        """
        Cleanup any remaining temporary files when the object is destroyed
        """
        if hasattr(self, '_created_files'):
            for file_path in self._created_files.copy():
                self.cleanup_file(file_path)