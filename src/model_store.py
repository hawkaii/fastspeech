"""
Model Store - Handles downloading and caching models from GCS
"""
import os
import logging
from pathlib import Path
from typing import Optional, Tuple
import threading
from google.cloud import storage

logger = logging.getLogger(__name__)


class ModelStore:
    """Manages model downloads from GCS and local caching"""
    
    def __init__(self, models_dir: str, gcs_bucket: Optional[str] = None):
        """
        Initialize ModelStore
        
        Args:
            models_dir: Local directory to store models
            gcs_bucket: GCS bucket URI (e.g., 'gs://my-bucket' or 'my-bucket')
        """
        self.models_dir = Path(models_dir)
        self.models_dir.mkdir(parents=True, exist_ok=True)
        
        self.gcs_bucket = None
        self.storage_client = None
        
        if gcs_bucket:
            # Remove gs:// prefix if present
            bucket_name = gcs_bucket.replace('gs://', '').strip('/')
            try:
                self.storage_client = storage.Client()
                self.gcs_bucket = self.storage_client.bucket(bucket_name)
                logger.info(f"Connected to GCS bucket: {bucket_name}")
            except Exception as e:
                logger.warning(f"Failed to connect to GCS: {e}. Using local models only.")
        
        # Thread lock for concurrent downloads
        self._download_locks = {}
        self._lock_mutex = threading.Lock()
    
    def _get_download_lock(self, key: str) -> threading.Lock:
        """Get or create a lock for a specific download key"""
        with self._lock_mutex:
            if key not in self._download_locks:
                self._download_locks[key] = threading.Lock()
            return self._download_locks[key]
    
    def get_model_path(self, language: str, gender: str) -> Path:
        """Get local path for model files"""
        return self.models_dir / language / gender / "model"
    
    def get_vocoder_path(self, language: str, gender: str) -> Path:
        """Get local path for vocoder files"""
        # Check language-specific vocoder first
        lang_vocoder = self.models_dir / "vocoder" / gender / language
        if lang_vocoder.exists():
            return lang_vocoder
        
        # Fall back to Aryan/Dravidian group vocoder
        aryan = self.models_dir / "vocoder" / gender / "aryan"
        if aryan.exists():
            return aryan
        
        # Return expected path anyway
        return lang_vocoder
    
    def model_exists_locally(self, language: str, gender: str) -> bool:
        """Check if model files exist locally"""
        model_path = self.get_model_path(language, gender)
        required_files = [
            'config.yaml',
            'model.pth',
            'feats_stats.npz',
            'pitch_stats.npz',
            'energy_stats.npz'
        ]
        return all((model_path / f).exists() for f in required_files)
    
    def vocoder_exists_locally(self, language: str, gender: str) -> bool:
        """Check if vocoder files exist locally"""
        vocoder_path = self.get_vocoder_path(language, gender)
        required_files = ['config.json', 'generator']
        return all((vocoder_path / f).exists() for f in required_files)
    
    def download_from_gcs(self, gcs_prefix: str, local_path: Path) -> bool:
        """
        Download files from GCS to local path
        
        Args:
            gcs_prefix: GCS path prefix (e.g., 'hindi/male/model')
            local_path: Local destination directory
        
        Returns:
            True if download successful, False otherwise
        """
        if not self.gcs_bucket:
            logger.error("GCS bucket not configured")
            return False
        
        try:
            local_path.mkdir(parents=True, exist_ok=True)
            
            # List and download all files with the prefix
            blobs = list(self.gcs_bucket.list_blobs(prefix=gcs_prefix))
            
            if not blobs:
                logger.warning(f"No files found in GCS with prefix: {gcs_prefix}")
                return False
            
            logger.info(f"Downloading {len(blobs)} files from gs://{self.gcs_bucket.name}/{gcs_prefix}")
            
            for blob in blobs:
                # Skip directory markers
                if blob.name.endswith('/'):
                    continue
                
                # Calculate relative path
                rel_path = blob.name[len(gcs_prefix):].lstrip('/')
                if not rel_path:
                    # This is the prefix itself (directory marker)
                    continue
                
                dest_file = local_path / rel_path
                dest_file.parent.mkdir(parents=True, exist_ok=True)
                
                logger.debug(f"Downloading {blob.name} -> {dest_file}")
                blob.download_to_filename(str(dest_file))
            
            logger.info(f"Successfully downloaded to {local_path}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to download from GCS: {e}", exc_info=True)
            return False
    
    def ensure_model(self, language: str, gender: str) -> Tuple[bool, str]:
        """
        Ensure model files are available locally, download from GCS if needed
        
        Returns:
            Tuple of (success: bool, message: str)
        """
        lock_key = f"model_{language}_{gender}"
        lock = self._get_download_lock(lock_key)
        
        with lock:
            # Check if already exists
            if self.model_exists_locally(language, gender):
                logger.debug(f"Model {language}/{gender} already exists locally")
                return True, "Model exists locally"
            
            # Try to download from GCS
            if self.gcs_bucket:
                logger.info(f"Downloading model {language}/{gender} from GCS...")
                gcs_prefix = f"{language}/{gender}/model"
                local_path = self.get_model_path(language, gender)
                
                if self.download_from_gcs(gcs_prefix, local_path):
                    if self.model_exists_locally(language, gender):
                        return True, "Model downloaded from GCS"
                    else:
                        return False, "Download completed but required files missing"
                else:
                    return False, "Failed to download model from GCS"
            else:
                return False, "Model not found locally and GCS not configured"
    
    def ensure_vocoder(self, language: str, gender: str) -> Tuple[bool, str]:
        """
        Ensure vocoder files are available locally, download from GCS if needed
        
        Returns:
            Tuple of (success: bool, message: str)
        """
        lock_key = f"vocoder_{language}_{gender}"
        lock = self._get_download_lock(lock_key)
        
        with lock:
            # Check if already exists
            if self.vocoder_exists_locally(language, gender):
                logger.debug(f"Vocoder for {language}/{gender} already exists locally")
                return True, "Vocoder exists locally"
            
            # Try to download from GCS
            if self.gcs_bucket:
                logger.info(f"Downloading vocoder {language}/{gender} from GCS...")
                
                # Try language-specific vocoder first
                gcs_prefix = f"vocoder/{gender}/{language}"
                local_path = self.models_dir / "vocoder" / gender / language
                
                if self.download_from_gcs(gcs_prefix, local_path):
                    if self.vocoder_exists_locally(language, gender):
                        return True, "Vocoder downloaded from GCS"
                
                # Try Aryan group vocoder as fallback
                logger.info(f"Trying Aryan group vocoder for {language}/{gender}...")
                gcs_prefix = f"vocoder/{gender}/aryan"
                local_path = self.models_dir / "vocoder" / gender / "aryan"
                
                if self.download_from_gcs(gcs_prefix, local_path):
                    if self.vocoder_exists_locally(language, gender):
                        return True, "Vocoder downloaded from GCS (aryan)"
                
                return False, "Failed to download vocoder from GCS"
            else:
                return False, "Vocoder not found locally and GCS not configured"
    
    def list_available_models(self) -> dict:
        """
        List all locally available language/gender combinations
        
        Returns:
            Dictionary mapping language -> list of genders
        """
        available = {}
        
        # Scan local models directory
        if not self.models_dir.exists():
            return available
        
        for lang_dir in self.models_dir.iterdir():
            if not lang_dir.is_dir() or lang_dir.name == 'vocoder':
                continue
            
            language = lang_dir.name
            genders = []
            
            for gender_dir in lang_dir.iterdir():
                if not gender_dir.is_dir():
                    continue
                
                gender = gender_dir.name
                
                # Check if model files exist
                if self.model_exists_locally(language, gender):
                    genders.append(gender)
            
            if genders:
                available[language] = sorted(genders)
        
        return available
