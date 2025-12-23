"""
Indic TTS API Server
Flask-based REST API for FastSpeech2 + HiFi-GAN Text-to-Speech synthesis
"""
import os
import io
import logging
from flask import Flask, request, jsonify, send_file
from werkzeug.exceptions import BadRequest, InternalServerError
import numpy as np
from scipy.io.wavfile import write as write_wav

from src.tts_engine import TTSEngine
from src.config import Config

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)
config = Config()

# Initialize TTS Engine (lazy loading)
tts_engine = None


def get_tts_engine():
    """Get or create TTS engine instance"""
    global tts_engine
    if tts_engine is None:
        logger.info("Initializing TTS Engine...")
        tts_engine = TTSEngine(config)
        logger.info("TTS Engine initialized successfully")
    return tts_engine


@app.route('/healthz', methods=['GET'])
def health_check():
    """Health check endpoint"""
    try:
        engine = get_tts_engine()
        return jsonify({
            'status': 'healthy',
            'device': engine.device,
            'models_loaded': len(engine.model_cache)
        }), 200
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        return jsonify({'status': 'unhealthy', 'error': str(e)}), 503


@app.route('/languages', methods=['GET'])
def list_languages():
    """List available languages and genders"""
    try:
        engine = get_tts_engine()
        available = engine.get_available_models()
        return jsonify({
            'languages': available,
            'count': sum(len(genders) for genders in available.values())
        }), 200
    except Exception as e:
        logger.error(f"Failed to list languages: {str(e)}")
        return jsonify({'error': str(e)}), 500


@app.route('/synthesize', methods=['POST'])
def synthesize():
    """
    Synthesize speech from text
    
    Request body (JSON):
    {
        "text": "Text to synthesize",
        "language": "hindi",
        "gender": "male",
        "alpha": 1.0  // optional, speed control (default 1.0)
    }
    
    Returns: audio/wav file
    """
    try:
        # Parse request
        if not request.is_json:
            raise BadRequest("Content-Type must be application/json")
        
        data = request.get_json()
        
        # Validate required fields
        text = data.get('text')
        language = data.get('language')
        gender = data.get('gender')
        
        if not text:
            raise BadRequest("'text' field is required")
        if not language:
            raise BadRequest("'language' field is required")
        if not gender:
            raise BadRequest("'gender' field is required")
        
        # Optional parameters
        alpha = float(data.get('alpha', 1.0))
        
        logger.info(f"Synthesis request: language={language}, gender={gender}, "
                   f"text_length={len(text)}, alpha={alpha}")
        
        # Get TTS engine and synthesize
        engine = get_tts_engine()
        audio_array = engine.synthesize(
            text=text,
            language=language,
            gender=gender,
            alpha=alpha
        )
        
        # Convert to WAV format in memory
        buffer = io.BytesIO()
        write_wav(buffer, engine.sampling_rate, audio_array)
        buffer.seek(0)
        
        logger.info(f"Synthesis successful: {len(audio_array)} samples generated")
        
        return send_file(
            buffer,
            mimetype='audio/wav',
            as_attachment=True,
            download_name=f'{language}_{gender}_output.wav'
        )
        
    except BadRequest as e:
        logger.warning(f"Bad request: {str(e)}")
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.error(f"Synthesis failed: {str(e)}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@app.route('/preload', methods=['POST'])
def preload_models():
    """
    Preload models for specific language/gender combinations
    
    Request body (JSON):
    {
        "models": [
            {"language": "hindi", "gender": "male"},
            {"language": "bengali", "gender": "female"}
        ]
    }
    """
    try:
        if not request.is_json:
            raise BadRequest("Content-Type must be application/json")
        
        data = request.get_json()
        models = data.get('models', [])
        
        if not isinstance(models, list):
            raise BadRequest("'models' must be a list")
        
        engine = get_tts_engine()
        loaded = []
        failed = []
        
        for model_spec in models:
            language = model_spec.get('language')
            gender = model_spec.get('gender')
            
            if not language or not gender:
                failed.append({'spec': model_spec, 'error': 'Missing language or gender'})
                continue
            
            try:
                engine.load_model(language, gender)
                loaded.append({'language': language, 'gender': gender})
                logger.info(f"Preloaded: {language}/{gender}")
            except Exception as e:
                failed.append({
                    'language': language,
                    'gender': gender,
                    'error': str(e)
                })
                logger.error(f"Failed to preload {language}/{gender}: {str(e)}")
        
        return jsonify({
            'loaded': loaded,
            'failed': failed,
            'total_cached': len(engine.model_cache)
        }), 200
        
    except Exception as e:
        logger.error(f"Preload failed: {str(e)}")
        return jsonify({'error': str(e)}), 500


@app.route('/', methods=['GET'])
def index():
    """API information endpoint"""
    return jsonify({
        'service': 'Indic TTS API',
        'version': '1.0.0',
        'endpoints': {
            'GET /': 'This information page',
            'GET /healthz': 'Health check',
            'GET /languages': 'List available languages',
            'POST /synthesize': 'Synthesize speech from text',
            'POST /preload': 'Preload models into memory'
        },
        'documentation': 'See README.md for detailed API usage'
    }), 200


@app.errorhandler(404)
def not_found(e):
    return jsonify({'error': 'Endpoint not found'}), 404


@app.errorhandler(500)
def internal_error(e):
    logger.error(f"Internal error: {str(e)}", exc_info=True)
    return jsonify({'error': 'Internal server error'}), 500


if __name__ == '__main__':
    # For development only
    app.run(host='0.0.0.0', port=8080, debug=False)
