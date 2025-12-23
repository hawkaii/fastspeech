"""
Configuration management for Indic TTS API
"""
import os
from typing import Optional, List, Tuple
from dotenv import load_dotenv

# Load environment variables from .env file if present
load_dotenv()


class Config:
    """Application configuration"""
    
    def __init__(self):
        # Model storage
        self.models_dir = os.getenv('MODELS_DIR', '/models')
        self.gcs_bucket = os.getenv('GCS_BUCKET', None)
        
        # Device configuration
        self.device = os.getenv('DEVICE', 'cuda')  # 'cuda' or 'cpu'
        
        # Preload models on startup
        self.preload_models = self._parse_preload_models()
        
        # API configuration
        self.host = os.getenv('HOST', '0.0.0.0')
        self.port = int(os.getenv('PORT', 8080))
        self.workers = int(os.getenv('WORKERS', 1))
        
        # Synthesis parameters
        self.sampling_rate = int(os.getenv('SAMPLING_RATE', 22050))
        self.max_text_length = int(os.getenv('MAX_TEXT_LENGTH', 5000))
        self.chunk_words = int(os.getenv('CHUNK_WORDS', 100))
        
        # Logging
        self.log_level = os.getenv('LOG_LEVEL', 'INFO')
    
    def _parse_preload_models(self) -> List[Tuple[str, str]]:
        """
        Parse PRELOAD_MODELS environment variable
        
        Format: "hindi:male,bengali:female,tamil:male"
        
        Returns:
            List of (language, gender) tuples
        """
        preload_str = os.getenv('PRELOAD_MODELS', '')
        if not preload_str:
            return []
        
        models = []
        for item in preload_str.split(','):
            item = item.strip()
            if not item:
                continue
            
            parts = item.split(':')
            if len(parts) == 2:
                language, gender = parts[0].strip(), parts[1].strip()
                if language and gender:
                    models.append((language, gender))
        
        return models
    
    def __repr__(self):
        return (
            f"Config(models_dir={self.models_dir}, "
            f"gcs_bucket={self.gcs_bucket}, "
            f"device={self.device}, "
            f"preload_models={self.preload_models})"
        )
