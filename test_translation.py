import requests
import sys

# Base URL for API
BASE_URL = "http://localhost:8000"

def translate_text(text, target_language):
    """Translate text to the target language using the translation API."""
    try:
        print(f"Sending translation request for: '{text}' to language '{target_language}'")
        
        response = requests.post(
            f"{BASE_URL}/translate",
            json={"text": text, "target_language": target_language}
        )
        
        print(f"Response status code: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            translated = result.get("translated_text")
            print(f"Translation successful: '{translated}'")
            return translated
        else:
            print(f"Translation failed: {response.text}")
            return None
    except Exception as e:
        print(f"Error during translation: {str(e)}")
        return None

def test_translations(text):
    """Test translations in multiple languages."""
    languages = {
        "urdu": "Urdu",
        "punjabi": "Punjabi", 
        "arabic": "Arabic",
        "sindhi": "Sindhi",
        "spanish": "Spanish",
        "french": "French",
        "german": "German",
        "chinese": "Chinese"
    }
    
    print("=" * 50)
    print(f"Testing translations for: '{text}'")
    print("=" * 50)
    
    results = {}
    
    for lang_code, lang_name in languages.items():
        print(f"\nTranslating to {lang_name}:")
        
        translated = translate_text(text, lang_code)
        results[lang_name] = translated
        
        # Print with direction indicators for RTL languages
        if lang_code in ["urdu", "arabic", "sindhi"]:
            if translated:
                rtl_display = f"<RTL> {translated} </RTL>"
                print(f"Display format: {rtl_display}")
    
    # Print summary of all translations
    print("\n" + "=" * 50)
    print("TRANSLATION RESULTS SUMMARY")
    print("=" * 50)
    
    for lang, translation in results.items():
        if translation:
            print(f"{lang.ljust(10)}: {translation}")
        else:
            print(f"{lang.ljust(10)}: FAILED")

if __name__ == "__main__":
    # Use command-line argument if provided, otherwise use default text
    text_to_translate = "My name is Yasir"
    
    if len(sys.argv) > 1:
        text_to_translate = " ".join(sys.argv[1:])
    
    test_translations(text_to_translate)
    
    print("\nTest complete!")