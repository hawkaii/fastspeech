#!/usr/bin/env python3
"""
Python client for testing Indic TTS API
"""
import requests
import argparse
import sys
from pathlib import Path


class TTSClient:
    """Simple client for Indic TTS API"""
    
    def __init__(self, base_url: str = "http://localhost:8080"):
        self.base_url = base_url.rstrip('/')
    
    def health_check(self):
        """Check API health"""
        response = requests.get(f"{self.base_url}/healthz")
        response.raise_for_status()
        return response.json()
    
    def list_languages(self):
        """List available languages"""
        response = requests.get(f"{self.base_url}/languages")
        response.raise_for_status()
        return response.json()
    
    def synthesize(self, text: str, language: str, gender: str, 
                   alpha: float = 1.0, output_file: str = None):
        """
        Synthesize speech from text
        
        Args:
            text: Input text
            language: Target language
            gender: Voice gender (male/female)
            alpha: Speed control (default 1.0)
            output_file: Path to save audio file
        
        Returns:
            Audio bytes
        """
        payload = {
            "text": text,
            "language": language,
            "gender": gender,
            "alpha": alpha
        }
        
        response = requests.post(
            f"{self.base_url}/synthesize",
            json=payload,
            headers={"Content-Type": "application/json"}
        )
        response.raise_for_status()
        
        audio_data = response.content
        
        if output_file:
            Path(output_file).write_bytes(audio_data)
            print(f"Audio saved to: {output_file}")
        
        return audio_data
    
    def preload_models(self, models: list):
        """
        Preload models into memory
        
        Args:
            models: List of dicts with 'language' and 'gender' keys
        """
        payload = {"models": models}
        response = requests.post(
            f"{self.base_url}/preload",
            json=payload,
            headers={"Content-Type": "application/json"}
        )
        response.raise_for_status()
        return response.json()


def main():
    parser = argparse.ArgumentParser(description="Indic TTS API Client")
    parser.add_argument("--url", default="http://localhost:8080",
                       help="API base URL")
    
    subparsers = parser.add_subparsers(dest="command", help="Command to execute")
    
    # Health check
    subparsers.add_parser("health", help="Check API health")
    
    # List languages
    subparsers.add_parser("languages", help="List available languages")
    
    # Synthesize
    synth_parser = subparsers.add_parser("synthesize", help="Synthesize speech")
    synth_parser.add_argument("text", help="Text to synthesize")
    synth_parser.add_argument("--language", required=True, help="Target language")
    synth_parser.add_argument("--gender", required=True, choices=["male", "female"],
                             help="Voice gender")
    synth_parser.add_argument("--alpha", type=float, default=1.0,
                             help="Speed control (default: 1.0)")
    synth_parser.add_argument("--output", required=True,
                             help="Output audio file path")
    
    # Preload
    preload_parser = subparsers.add_parser("preload", help="Preload models")
    preload_parser.add_argument("models", nargs="+",
                               help="Models to preload (format: language:gender)")
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        sys.exit(1)
    
    client = TTSClient(args.url)
    
    try:
        if args.command == "health":
            result = client.health_check()
            print("Health Check:")
            print(f"  Status: {result.get('status')}")
            print(f"  Device: {result.get('device')}")
            print(f"  Models Loaded: {result.get('models_loaded')}")
        
        elif args.command == "languages":
            result = client.list_languages()
            print("Available Languages:")
            for lang, genders in result.get('languages', {}).items():
                print(f"  {lang}: {', '.join(genders)}")
            print(f"Total: {result.get('count')} models")
        
        elif args.command == "synthesize":
            print(f"Synthesizing: {args.language}/{args.gender}")
            print(f"Text: {args.text}")
            print(f"Alpha: {args.alpha}")
            
            client.synthesize(
                text=args.text,
                language=args.language,
                gender=args.gender,
                alpha=args.alpha,
                output_file=args.output
            )
            print("Done!")
        
        elif args.command == "preload":
            models = []
            for model_str in args.models:
                try:
                    lang, gender = model_str.split(':')
                    models.append({"language": lang, "gender": gender})
                except ValueError:
                    print(f"Invalid model format: {model_str} (expected language:gender)")
                    sys.exit(1)
            
            result = client.preload_models(models)
            print(f"Loaded: {len(result.get('loaded', []))} models")
            print(f"Failed: {len(result.get('failed', []))} models")
            if result.get('failed'):
                print("Failed models:")
                for fail in result['failed']:
                    print(f"  {fail}")
    
    except requests.exceptions.RequestException as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Unexpected error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
