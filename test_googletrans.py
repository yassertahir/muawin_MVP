from googletrans import Translator
import sys
import os

def test_translations(text):
    """Test Google Translate in multiple languages."""
    translator = Translator()
    
    languages = {
        "ur": "Urdu",
        "pa": "Punjabi", 
        "ar": "Arabic",
        "sd": "Sindhi",
        "es": "Spanish",
        "fr": "French",
        "de": "German",
        "zh-cn": "Chinese"
    }
    
    print("=" * 50)
    print(f"Testing Google Translate for: '{text}'")
    print("=" * 50)
    
    results = {}
    html_content = [
        "<!DOCTYPE html>",
        "<html>",
        "<head>",
        "    <meta charset='UTF-8'>",
        "    <title>Translation Results</title>",
        "    <style>",
        "        body { font-family: Arial, sans-serif; margin: 20px; }",
        "        .rtl { direction: rtl; text-align: right; }",
        "        .ltr { direction: ltr; text-align: left; }",
        "        .translation { margin: 10px 0; padding: 10px; border: 1px solid #ccc; }",
        "        h2 { color: #333; }",
        "    </style>",
        "</head>",
        "<body>",
        f"    <h1>Translations for: '{text}'</h1>"
    ]
    
    for lang_code, lang_name in languages.items():
        print(f"\nTranslating to {lang_name}:")
        
        try:
            translated = translator.translate(text, dest=lang_code)
            results[lang_name] = {
                "text": translated.text,
                "pronunciation": getattr(translated, 'pronunciation', None)
            }
            
            print(f"✓ Translation: {translated.text}")
            if hasattr(translated, 'pronunciation') and translated.pronunciation:
                print(f"  Pronunciation: {translated.pronunciation}")
            
            # Add to HTML with proper RTL/LTR formatting
            is_rtl = lang_code in ["ur", "ar", "sd"]
            direction_class = "rtl" if is_rtl else "ltr"
            
            html_content.append(f"    <div class='translation'>")
            html_content.append(f"        <h2>{lang_name}</h2>")
            html_content.append(f"        <div class='{direction_class}'>{translated.text}</div>")
            
            if hasattr(translated, 'pronunciation') and translated.pronunciation:
                html_content.append(f"        <p>Pronunciation: {translated.pronunciation}</p>")
                
            html_content.append(f"    </div>")
        except Exception as e:
            print(f"✗ Error: {str(e)}")
            results[lang_name] = {"error": str(e)}
    
    # Print summary of all translations
    print("\n" + "=" * 50)
    print("TRANSLATION RESULTS SUMMARY")
    print("=" * 50)
    
    for lang, translation in results.items():
        if "error" not in translation:
            print(f"{lang.ljust(10)}: {translation['text']}")
        else:
            print(f"{lang.ljust(10)}: FAILED - {translation['error']}")
    
    # Finalize HTML content
    html_content.append("</body>")
    html_content.append("</html>")
    
    # Save HTML to file
    output_file = "translation_results.html"
    with open(output_file, "w", encoding="utf-8") as file:
        file.write("\n".join(html_content))
    
    print(f"\nHTML results saved to {output_file}")

if __name__ == "__main__":
    # Use command-line argument if provided, otherwise use default text
    text_to_translate = "My name is Yasir"
    
    if len(sys.argv) > 1:
        text_to_translate = " ".join(sys.argv[1:])
    
    test_translations(text_to_translate)
    
    print("\nTest complete!")