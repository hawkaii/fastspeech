"""
Preprocessing module initialization
This module imports the original text preprocessing code from the cloned Fastspeech2_HS repository
"""
import sys
import os

# Add the cloned repository to path
preprocessing_path = '/tmp/fs2'
if os.path.exists(preprocessing_path):
    sys.path.insert(0, preprocessing_path)

# Try to import from cloned repo, fall back to stub if not available
try:
    from text_preprocess_for_inference import (
        TTSDurAlignPreprocessor,
        CharTextPreprocessor,
        TTSPreprocessor
    )
    __all__ = ['TTSDurAlignPreprocessor', 'CharTextPreprocessor', 'TTSPreprocessor']
except ImportError:
    # Preprocessing code not available, will use stub from text_processor.py
    __all__ = []
