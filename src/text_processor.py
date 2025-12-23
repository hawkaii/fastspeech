"""
Text Preprocessing Factory
Provides appropriate text preprocessor based on language
"""
import logging

logger = logging.getLogger(__name__)


class TextPreprocessorFactory:
    """Factory for creating appropriate text preprocessors"""
    
    @staticmethod
    def get_preprocessor(language: str):
        """
        Get appropriate preprocessor for language
        
        Args:
            language: Target language code
        
        Returns:
            Preprocessor instance
        """
        # Import here to avoid circular dependencies
        # These will be loaded from the original repo code
        try:
            from preprocessing.text_preprocess_for_inference import (
                TTSDurAlignPreprocessor,
                CharTextPreprocessor,
                TTSPreprocessor
            )
        except ImportError:
            # Fallback to local implementation
            logger.warning("Using stub preprocessor - text processing may be limited")
            return StubPreprocessor()
        
        # Select preprocessor based on language
        if language in ['urdu', 'punjabi']:
            return CharTextPreprocessor()
        elif language == 'english':
            return TTSPreprocessor()
        else:
            return TTSDurAlignPreprocessor()


class StubPreprocessor:
    """Stub preprocessor for testing without full dependencies"""
    
    def preprocess(self, text: str, language: str, gender: str):
        """
        Basic preprocessing - just clean and split
        
        Returns:
            (preprocessed_text_list, phrases_list)
        """
        import re
        
        # Basic cleaning
        text = re.sub(r'[#\n\r]+', ' ', text)
        text = re.sub(r'\s+', ' ', text)
        text = text.strip()
        
        # Split by punctuation
        phrases = re.split(r'[.!?;।]+', text)
        phrases = [p.strip() for p in phrases if p.strip()]
        
        logger.warning("Using stub preprocessor - results may not be optimal")
        return phrases, phrases
