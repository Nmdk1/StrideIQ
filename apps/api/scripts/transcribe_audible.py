#!/usr/bin/env python3
"""
Audible Transcription Script

Transcribes Audible audiobook files to text for knowledge extraction.
Uses OpenAI Whisper for speech-to-text transcription.

Note: This requires:
1. Converting .aax to .mp3/.wav (may require Audible download + conversion tools)
2. Speech-to-text transcription (Whisper API or local model)
"""
import sys
import os
from pathlib import Path

try:
    import whisper
    WHISPER_LOCAL_AVAILABLE = True
except ImportError:
    WHISPER_LOCAL_AVAILABLE = False

try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False


def transcribe_with_whisper_api(audio_file: str, api_key: str = None) -> str:
    """
    Transcribe audio using OpenAI Whisper API.
    
    Args:
        audio_file: Path to audio file (.mp3, .wav, .m4a)
        api_key: OpenAI API key (or use OPENAI_API_KEY env var)
        
    Returns:
        Transcribed text
    """
    if not OPENAI_AVAILABLE:
        return ""
    
    client = OpenAI(api_key=api_key or os.getenv("OPENAI_API_KEY"))
    
    try:
        with open(audio_file, 'rb') as audio:
            transcript = client.audio.transcriptions.create(
                model="whisper-1",
                file=audio,
                response_format="text"
            )
        return transcript
    except Exception as e:
        print(f"Error transcribing with Whisper API: {e}")
        return ""


def transcribe_with_local_whisper(audio_file: str) -> str:
    """
    Transcribe audio using local Whisper model.
    
    Requires: pip install openai-whisper
    Downloads model on first use (~1.5GB)
    
    Args:
        audio_file: Path to audio file
        
    Returns:
        Transcribed text
    """
    if not WHISPER_LOCAL_AVAILABLE:
        return ""
    
    try:
        model = whisper.load_model("base")  # or "small", "medium", "large"
        result = model.transcribe(audio_file)
        return result["text"]
    except Exception as e:
        print(f"Error transcribing with local Whisper: {e}")
        return ""


def transcribe_audio(audio_file: str, use_api: bool = True) -> str:
    """
    Transcribe audio file to text.
    
    Args:
        audio_file: Path to audio file
        use_api: If True, use OpenAI API; if False, use local Whisper
        
    Returns:
        Transcribed text
    """
    print(f"Transcribing {audio_file}...")
    print("Note: This may take a while for long audiobooks.")
    
    if use_api and OPENAI_AVAILABLE:
        print("Using OpenAI Whisper API...")
        text = transcribe_with_whisper_api(audio_file)
        if text:
            return text
    
    if WHISPER_LOCAL_AVAILABLE:
        print("Using local Whisper model...")
        text = transcribe_with_local_whisper(audio_file)
        if text:
            return text
    
    print("❌ No transcription method available.")
    print("Install one of:")
    print("  1. OpenAI API: pip install openai (requires API key)")
    print("  2. Local Whisper: pip install openai-whisper")
    return ""


def main():
    """Main function for command-line usage."""
    if len(sys.argv) < 3:
        print("Usage: python transcribe_audible.py <audio_file> <output_text_file> [--local]")
        print("\nNote: Audio file must be .mp3, .wav, or .m4a format")
        print("      Audible .aax files need conversion first (see guide)")
        print("\nExample:")
        print("  python transcribe_audible.py daniels_audio.mp3 daniels_text.txt")
        print("  python transcribe_audible.py daniels_audio.mp3 daniels_text.txt --local")
        sys.exit(1)
    
    audio_file = sys.argv[1]
    output_file = sys.argv[2]
    use_local = "--local" in sys.argv
    
    # Check file exists
    if not os.path.exists(audio_file):
        print(f"❌ Audio file not found: {audio_file}")
        sys.exit(1)
    
    # Transcribe
    text = transcribe_audio(audio_file, use_api=not use_local)
    
    if not text:
        print("❌ Transcription failed")
        sys.exit(1)
    
    # Write to output file
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(text)
    
    print(f"✅ Transcribed {len(text)} characters to {output_file}")
    print(f"✅ Ready for knowledge extraction!")


if __name__ == "__main__":
    main()

