"""
TTS Engine - Core text-to-speech synthesis engine
Integrates FastSpeech2 model, HiFi-GAN vocoder, and text preprocessing
"""
import os
import sys
import logging
import re
import json
from pathlib import Path
from typing import Optional, Dict, Tuple
import numpy as np
import torch
import yaml
import concurrent.futures

# Add hifigan to path
sys.path.insert(0, '/app/hifigan')

from espnet2.bin.tts_inference import Text2Speech
from models import Generator
from env import AttrDict

from src.model_store import ModelStore
from src.config import Config
from src.text_processor import TextPreprocessorFactory

logger = logging.getLogger(__name__)

SAMPLING_RATE = 22050
MAX_WAV_VALUE = 32768.0


class TTSEngine:
    """Main TTS synthesis engine"""
    
    def __init__(self, config: Config):
        """
        Initialize TTS Engine
        
        Args:
            config: Application configuration
        """
        self.config = config
        self.sampling_rate = config.sampling_rate
        
        # Determine device
        if config.device == 'cuda' and torch.cuda.is_available():
            self.device = 'cuda'
            logger.info(f"Using GPU: {torch.cuda.get_device_name(0)}")
        else:
            self.device = 'cpu'
            logger.info("Using CPU")
        
        # Initialize model store
        self.model_store = ModelStore(
            models_dir=config.models_dir,
            gcs_bucket=config.gcs_bucket
        )
        
        # Cache for loaded models: key = (language, gender)
        self.model_cache: Dict[Tuple[str, str], Tuple] = {}
        
        # Preload models if configured
        if config.preload_models:
            self._preload_models()
    
    def _preload_models(self):
        """Preload configured models into memory"""
        logger.info(f"Preloading {len(self.config.preload_models)} models...")
        for language, gender in self.config.preload_models:
            try:
                self.load_model(language, gender)
                logger.info(f"Preloaded: {language}/{gender}")
            except Exception as e:
                logger.error(f"Failed to preload {language}/{gender}: {e}")
    
    def load_vocoder(self, language: str, gender: str):
        """Load HiFi-GAN vocoder model"""
        # Ensure vocoder files are available
        success, msg = self.model_store.ensure_vocoder(language, gender)
        if not success:
            raise RuntimeError(f"Vocoder not available: {msg}")
        
        vocoder_path = self.model_store.get_vocoder_path(language, gender)
        
        config_file = vocoder_path / "config.json"
        generator_file = vocoder_path / "generator"
        
        if not config_file.exists():
            raise FileNotFoundError(f"Vocoder config not found: {config_file}")
        if not generator_file.exists():
            raise FileNotFoundError(f"Vocoder generator not found: {generator_file}")
        
        # Load configuration
        with open(config_file, 'r') as f:
            data = f.read()
        json_config = json.loads(data)
        h = AttrDict(json_config)
        
        torch.manual_seed(h.seed)
        
        # Create and load generator
        device = torch.device(self.device)
        generator = Generator(h).to(device)
        
        state_dict_g = torch.load(generator_file, map_location=device)
        generator.load_state_dict(state_dict_g['generator'])
        generator.eval()
        generator.remove_weight_norm()
        
        logger.info(f"Loaded vocoder: {vocoder_path}")
        return generator
    
    def load_fastspeech2(self, language: str, gender: str):
        """Load FastSpeech2 TTS model"""
        # Ensure model files are available
        success, msg = self.model_store.ensure_model(language, gender)
        if not success:
            raise RuntimeError(f"Model not available: {msg}")
        
        model_path = self.model_store.get_model_path(language, gender)
        
        config_file = model_path / "config.yaml"
        model_file = model_path / "model.pth"
        
        if not config_file.exists():
            raise FileNotFoundError(f"Model config not found: {config_file}")
        if not model_file.exists():
            raise FileNotFoundError(f"Model file not found: {model_file}")
        
        # Update config.yaml with absolute paths for stats files
        with open(config_file, "r") as f:
            config = yaml.safe_load(f)
        
        feat_path = model_path / "feats_stats.npz"
        pitch_path = model_path / "pitch_stats.npz"
        energy_path = model_path / "energy_stats.npz"
        
        config["normalize_conf"]["stats_file"] = str(feat_path)
        config["pitch_normalize_conf"]["stats_file"] = str(pitch_path)
        config["energy_normalize_conf"]["stats_file"] = str(energy_path)
        
        # Write updated config
        with open(config_file, "w") as f:
            yaml.dump(config, f)
        
        # Load model
        tts_model = Text2Speech(
            train_config=str(config_file),
            model_file=str(model_file),
            device=self.device
        )
        
        logger.info(f"Loaded FastSpeech2 model: {model_path}")
        return tts_model
    
    def load_model(self, language: str, gender: str) -> Tuple:
        """
        Load or retrieve cached model and vocoder
        
        Returns:
            Tuple of (fastspeech2_model, vocoder, preprocessor)
        """
        cache_key = (language, gender)
        
        if cache_key in self.model_cache:
            logger.debug(f"Using cached model: {language}/{gender}")
            return self.model_cache[cache_key]
        
        logger.info(f"Loading model: {language}/{gender}")
        
        # Load models
        fs2_model = self.load_fastspeech2(language, gender)
        vocoder = self.load_vocoder(language, gender)
        
        # Get appropriate preprocessor
        preprocessor = TextPreprocessorFactory.get_preprocessor(language)
        
        # Cache the loaded models
        self.model_cache[cache_key] = (fs2_model, vocoder, preprocessor)
        
        logger.info(f"Model loaded and cached: {language}/{gender}")
        return self.model_cache[cache_key]
    
    def extract_text_alpha_chunks(self, text: str, default_alpha: float = 1.0):
        """
        Extract text chunks with alpha and silence tags
        
        Supports:
        - <alpha=1.2> for speed control
        - <sil=500ms> or <sil=2s> for silence insertion
        
        Returns:
            List of tuples: (text, alpha, is_silence, silence_duration)
        """
        alpha_pattern = r"<alpha=([0-9.]+)>"
        sil_pattern = r"<sil=([0-9.]+)(ms|s)>"
        
        chunks = []
        alpha = default_alpha
        
        # Split by alpha tags
        alpha_blocks = re.split(alpha_pattern, text)
        i = 0
        
        while i < len(alpha_blocks):
            if i == 0:
                current_block = alpha_blocks[i]
                i += 1
            else:
                alpha = float(alpha_blocks[i])
                i += 1
                current_block = alpha_blocks[i] if i < len(alpha_blocks) else ""
                i += 1
            
            # Find silence tags in current block
            sil_matches = list(re.finditer(sil_pattern, current_block))
            sil_placeholders = {}
            
            for j, match in enumerate(sil_matches):
                tag = match.group(0)
                value = float(match.group(1))
                unit = match.group(2)
                duration = value / 1000.0 if unit == "ms" else value
                placeholder = f"__SIL_{j}__"
                sil_placeholders[placeholder] = duration
                current_block = current_block.replace(tag, f" {placeholder} ")
            
            # Split by sentences
            sentences = [s.strip() for s in current_block.split('.') if s.strip()]
            
            for sentence in sentences:
                words = sentence.split()
                buffer = []
                
                for word in words:
                    if word in sil_placeholders:
                        if buffer:
                            chunks.append((" ".join(buffer), alpha, False, None))
                            buffer = []
                        chunks.append(("", alpha, True, sil_placeholders[word]))
                    else:
                        buffer.append(word)
                
                if buffer:
                    chunks.append((" ".join(buffer), alpha, False, None))
        
        return chunks
    
    def split_into_chunks(self, text: str, words_per_chunk: int = 100):
        """Split text into word chunks for processing"""
        words = text.split()
        chunks = [words[i:i + words_per_chunk] 
                 for i in range(0, len(words), words_per_chunk)]
        return [' '.join(chunk) for chunk in chunks]
    
    def synthesize_chunk(self, text: str, model, vocoder, alpha: float):
        """Synthesize a single chunk of text"""
        with torch.inference_mode():
            # Generate mel-spectrograms
            out = model(text, decode_conf={"alpha": alpha})
            
            x = out["feat_gen_denorm"].T.unsqueeze(0) * 2.3262
            x = x.to(self.device)
            
            # Generate audio with vocoder
            y_g_hat = vocoder(x)
            audio = y_g_hat.squeeze()
            audio = audio * MAX_WAV_VALUE
            audio = audio.cpu().numpy().astype('int16')
            
            return audio
    
    def synthesize(self, text: str, language: str, gender: str, 
                   alpha: float = 1.0) -> np.ndarray:
        """
        Synthesize speech from text
        
        Args:
            text: Input text (supports <alpha> and <sil> tags)
            language: Target language
            gender: Voice gender (male/female)
            alpha: Default speed control (1.0 = normal, >1 = slower, <1 = faster)
        
        Returns:
            Audio array (int16)
        """
        # Validate text length
        if len(text) > self.config.max_text_length:
            raise ValueError(
                f"Text too long ({len(text)} chars). "
                f"Maximum: {self.config.max_text_length}"
            )
        
        # Load model, vocoder, and preprocessor
        model, vocoder, preprocessor = self.load_model(language, gender)
        
        # Extract chunks with alpha and silence tags
        text_alpha_chunks = self.extract_text_alpha_chunks(text, alpha)
        
        audio_arr = []
        
        # Process each chunk
        with concurrent.futures.ThreadPoolExecutor() as executor:
            futures = []
            
            for chunk_text, alpha_val, is_silence, sil_duration in text_alpha_chunks:
                if is_silence:
                    # Generate silence
                    silence_samples = int(sil_duration * self.sampling_rate)
                    silence_audio = np.zeros(silence_samples, dtype=np.int16)
                    futures.append(silence_audio)
                else:
                    if not chunk_text.strip():
                        continue
                    
                    # Preprocess text
                    preprocessed_text, _ = preprocessor.preprocess(
                        chunk_text, language, gender
                    )
                    preprocessed_text = " ".join(preprocessed_text)
                    
                    # Submit synthesis task
                    future = executor.submit(
                        self.synthesize_chunk,
                        preprocessed_text,
                        model,
                        vocoder,
                        alpha_val
                    )
                    futures.append(future)
            
            # Collect results
            for item in futures:
                if isinstance(item, np.ndarray):
                    audio_arr.append(item)
                else:
                    audio_arr.append(item.result())
        
        # Concatenate all audio chunks
        if not audio_arr:
            # Return silence if no audio generated
            return np.zeros(int(0.5 * self.sampling_rate), dtype=np.int16)
        
        result_array = np.concatenate(audio_arr, axis=0)
        return result_array
    
    def get_available_models(self) -> dict:
        """Get dictionary of available language/gender combinations"""
        return self.model_store.list_available_models()
