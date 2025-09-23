import os
import requests
import google.generativeai as genai
import base64
import logging
import time
from flask import Flask, request, jsonify, render_template
from dotenv import load_dotenv

# --- 1. बेसिक सेटअप और कॉन्फ़िगरेशन ---

# लॉगिंग कॉन्फ़िगर करें ताकि Render पर डिबगिंग आसान हो
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# लोकल डेवलपमेंट के लिए .env फाइल से वेरिएबल्स लोड करें
load_dotenv()

# Flask ऐप को इनिशियलाइज़ करें
# template_folder='.' का मतलब है कि index.html इसी फोल्डर में है
app = Flask(__name__, template_folder='.')

# --- 2. API और मॉडल कॉन्फ़िगरेशन ---

# API कीज़ को एनवायरनमेंट वेरिएबल्स से सुरक्षित रूप से लोड करें
try:
    GEMINI_API_KEY = os.environ['GEMINI_API_KEY']
    ELEVENLABS_API_KEY = os.environ['ELEVENLABS_API_KEY']
    logging.info("API keys loaded successfully.")
except KeyError as e:
    logging.error(f"FATAL ERROR: Environment variable not set: {e}")
    raise RuntimeError(f"FATAL ERROR: Environment variable not set: {e}. Please set it in Render's environment variables.")

# API URLs और मॉडल IDs को एक जगह रखें
ELEVENLABS_API_URL = "https://api.elevenlabs.io/v1"
ELEVENLABS_MODEL_ID = "eleven_multilingual_v2"
GEMINI_MODEL_ID = 'gemini-1.5-pro-latest'

# Gemini AI मॉडल को कॉन्फ़िगर करें
try:
    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel(GEMINI_MODEL_ID)
    logging.info(f"Gemini model '{GEMINI_MODEL_ID}' configured successfully.")
except Exception as e:
    logging.error(f"Failed to configure Gemini AI: {e}")
    raise

# --- 3. वॉयस लिस्ट के लिए सर्वर-साइड कैशिंग ---

# आवाज़ों की लिस्ट को कैश करें ताकि बार-बार API कॉल न हो
# यह परफॉरमेंस को बढ़ाता है और API का उपयोग बचाता है
voices_cache = {
    "data": None,
    "timestamp": 0
}
VOICES_CACHE_DURATION_SECONDS = 3600  # 1 घंटा

# --- 4. Flask रूट्स और API एंडपॉइंट्स ---

@app.route('/')
def index():
    """मुख्य index.html पेज को सर्व करता है।"""
    return render_template('index.html')

@app.route('/api/voices', methods=['GET'])
def get_voices():
    """ElevenLabs से आवाज़ों की लिस्ट लाता है और उन्हें कैश करता है।"""
    current_time = time.time()
    
    # अगर कैश वैलिड है, तो कैश से डेटा भेजें
    if voices_cache["data"] and (current_time - voices_cache["timestamp"] < VOICES_CACHE_DURATION_SECONDS):
        logging.info("Serving voices from cache.")
        return jsonify(voices_cache["data"])

    logging.info("Fetching fresh voices from ElevenLabs API.")
    url = f"{ELEVENLABS_API_URL}/voices"
    headers = {"Accept": "application/json", "xi-api-key": ELEVENLABS_API_KEY}
    
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()  # HTTP एरर के लिए चेक करें
        
        # कैश को अपडेट करें
        voices_data = response.json()
        voices_cache["data"] = voices_data
        voices_cache["timestamp"] = current_time
        
        return jsonify(voices_data)
    except requests.exceptions.RequestException as e:
        logging.error(f"Error fetching voices from ElevenLabs: {e}")
        return jsonify({"error": "Could not fetch voices from ElevenLabs API."}), 500

@app.route('/api/chat', methods=['POST'])
def chat():
    """यूज़र का मैसेज लेता है, Gemini से जवाब पाता है, और ElevenLabs से ऑडियो बनाता है।"""
    try:
        data = request.get_json()
        user_message = data.get('message')
        voice_id = data.get('voice_id')

        if not user_message or not voice_id:
            logging.warning("Missing message or voice_id in chat request.")
            return jsonify({"error": "Message and voice_id are required."}), 400

        logging.info(f"Processing chat request for voice_id: {voice_id}")

        # --- स्टेप A: Gemini से टेक्स्ट जवाब पाएँ ---
        try:
            gemini_response = model.generate_content(user_message)
            ai_text_response = gemini_response.text
        except Exception as e:
            logging.error(f"Gemini API error: {e}")
            return jsonify({"error": "Failed to get response from AI model."}), 500

        # --- स्टेप B: ElevenLabs से ऑडियो पाएँ ---
        tts_url = f"{ELEVENLABS_API_URL}/text-to-speech/{voice_id}"
        headers = {
            "Accept": "audio/mpeg",
            "Content-Type": "application/json",
            "xi-api-key": ELEVENLABS_API_KEY
        }
        tts_payload = {
            "text": ai_text_response,
            "model_id": ELEVENLABS_MODEL_ID,
            "voice_settings": {"stability": 0.5, "similarity_boost": 0.75}
        }
        
        try:
            audio_response = requests.post(tts_url, json=tts_payload, headers=headers)
            audio_response.raise_for_status()
        except requests.exceptions.RequestException as e:
            logging.error(f"ElevenLabs API error: {e}")
            return jsonify({"error": "Failed to generate audio from text."}), 500

        # --- स्टेप C: ऑडियो को Base64 में एन्कोड करें और जवाब भेजें ---
        audio_base64 = base64.b64encode(audio_response.content).decode('utf-8')

        logging.info("Successfully generated text and audio response.")
        return jsonify({
            "textResponse": ai_text_response,
            "audioBase64": audio_base64
        })

    except Exception as e:
        logging.error(f"An unexpected error occurred in /api/chat: {e}")
        return jsonify({"error": "An unexpected server error occurred."}), 500

# यह सुनिश्चित करता है कि ऐप लोकल डेवलपमेंट में चलाया जा सकता है।
# Render gunicorn का उपयोग करके इसे चलाएगा।
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))
