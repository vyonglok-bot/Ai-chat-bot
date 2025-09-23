# ==============================================================================
# J.A.R.V.I.S. AI ASSISTANT - BACKEND SERVER
# ==============================================================================
# This file contains the complete backend logic for the AI assistant,
# including API integrations with Google Gemini and ElevenLabs.
# It is designed for robustness, clarity, and easy debugging on platforms like Render.
# ==============================================================================

# --- 1. IMPORT NECESSARY LIBRARIES ---
# ------------------------------------------------------------------------------
import os
import requests
import google.generativeai as genai
import base64
import logging
import time
from flask import Flask, request, jsonify, render_template
from dotenv import load_dotenv

# --- 2. INITIAL SETUP AND CONFIGURATION ---
# ------------------------------------------------------------------------------

# Configure logging to provide detailed output in the Render server logs.
# This helps in tracking the application's flow and diagnosing issues.
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - [J.A.R.V.I.S. Backend] - %(message)s'
)

# Load environment variables from a .env file for local development.
# On Render, these variables will be set in the environment settings.
load_dotenv()

# Initialize the Flask web application.
# 'template_folder' is set to '.' to find 'index.html' in the root directory.
app = Flask(__name__, template_folder='.')
logging.info("Flask application initialized successfully.")


# --- 3. API KEYS AND SERVICE CONFIGURATION ---
# ------------------------------------------------------------------------------

# Securely load API keys from environment variables.
# The application will fail to start if these keys are not found.
try:
    GEMINI_API_KEY = os.environ['GEMINI_API_KEY']
    ELEVENLABS_API_KEY = os.environ['ELEVENLABS_API_KEY']
    logging.info("All required API keys have been loaded successfully.")
except KeyError as error:
    missing_key = str(error)
    logging.critical(f"FATAL ERROR: The environment variable {missing_key} is not set!")
    raise RuntimeError(f"The application cannot start because the environment variable {missing_key} is missing. Please set it in Render's environment variables.")

# Centralized configuration for API endpoints and models.
ELEVENLABS_API_URL = "https://api.elevenlabs.io/v1"
ELEVENLABS_MODEL_ID = "eleven_multilingual_v2"
GEMINI_MODEL_ID = 'gemini-1.5-pro-latest'

# Configure the Google Gemini client with the API key.
try:
    genai.configure(api_key=GEMINI_API_KEY)
    gemini_model = genai.GenerativeModel(GEMINI_MODEL_ID)
    logging.info(f"Google Gemini model '{GEMINI_MODEL_ID}' has been configured and is ready.")
except Exception as error:
    logging.critical(f"CRITICAL: Failed to configure the Gemini AI model. Error: {error}")
    raise

# --- 4. SERVER-SIDE CACHING FOR ELEVENLABS VOICES ---
# ------------------------------------------------------------------------------
# This caching mechanism stores the list of voices to avoid making redundant API calls,
# which improves performance and reduces API usage.

voices_cache = {
    "data": None,
    "last_fetched_timestamp": 0
}
# Cache duration is set to 1 hour (3600 seconds).
VOICES_CACHE_DURATION_SECONDS = 3600

# --- 5. FLASK WEB ROUTES AND API ENDPOINTS ---
# ------------------------------------------------------------------------------

@app.route('/')
def serve_main_page():
    """
    Serves the main user interface file (index.html).
    """
    logging.info("Request received for the main page. Serving index.html.")
    return render_template('index.html')


@app.route('/api/voices', methods=['GET'])
def get_elevenlabs_voices():
    """
    Provides the list of available voices from ElevenLabs, using a cache to
    optimize performance.
    """
    current_time = time.time()
    is_cache_valid = (current_time - voices_cache["last_fetched_timestamp"]) < VOICES_CACHE_DURATION_SECONDS

    if voices_cache["data"] and is_cache_valid:
        logging.info("Serving voices list from the cache.")
        return jsonify(voices_cache["data"])

    logging.info("Cache is invalid or empty. Fetching a fresh list of voices from ElevenLabs API.")
    api_url = f"{ELEVENLABS_API_URL}/voices"
    headers = {"Accept": "application/json", "xi-api-key": ELEVENLABS_API_KEY}
    
    try:
        response = requests.get(api_url, headers=headers)
        response.raise_for_status()  # This will raise an error for bad responses (4xx or 5xx)
        
        voices_data = response.json()
        voices_cache["data"] = voices_data
        voices_cache["last_fetched_timestamp"] = current_time
        logging.info("Successfully fetched and cached a new list of voices.")
        
        return jsonify(voices_data)
    except requests.exceptions.RequestException as error:
        logging.error(f"Failed to fetch voices from ElevenLabs API. Error: {error}")
        return jsonify({"error": "Could not connect to the voice generation service."}), 500


@app.route('/api/chat', methods=['POST'])
def handle_chat_request():
    """
    This is the core endpoint. It receives user input, gets a response from Gemini,
    generates audio with ElevenLabs, and returns both to the frontend.
    This function includes detailed error handling to diagnose API issues.
    """
    try:
        # --- Get data from the frontend request ---
        request_data = request.get_json()
        user_message = request_data.get('message')
        voice_id = request_data.get('voice_id')

        if not user_message or not voice_id:
            logging.warning("Chat request received with missing message or voice_id.")
            return jsonify({"error": "Both a message and a voice_id are required."}), 400

        logging.info(f"Processing new chat request. Selected voice_id: {voice_id}")

        # --- STEP A: Get a text response from the Google Gemini API ---
        try:
            logging.info("Sending user message to Gemini API...")
            gemini_response = gemini_model.generate_content(user_message)
            ai_text_response = gemini_response.text
            logging.info("Successfully received response from Gemini API.")
        except Exception as error:
            # THIS IS THE MOST IMPORTANT PART FOR DEBUGGING
            # It captures the exact error from Google and sends it to the frontend.
            google_error_message = str(error)
            logging.error(f"CRITICAL: An error occurred with the Gemini API. Full Error: {google_error_message}")
            # Return the detailed error to the frontend so the user can see it.
            return jsonify({"error": f"AI Model Error: {google_error_message}"}), 500

        # --- STEP B: Generate audio from the text using ElevenLabs API ---
        try:
            logging.info("Sending AI text response to ElevenLabs API for audio generation...")
            tts_url = f"{ELEVENLABS_API_URL}/text-to-speech/{voice_id}"
            headers = {"Accept": "audio/mpeg", "Content-Type": "application/json", "xi-api-key": ELEVENLABS_API_KEY}
            tts_payload = {
                "text": ai_text_response,
                "model_id": ELEVENLABS_MODEL_ID,
                "voice_settings": {"stability": 0.5, "similarity_boost": 0.75}
            }
            
            audio_response = requests.post(tts_url, json=tts_payload, headers=headers)
            audio_response.raise_for_status()
            logging.info("Successfully received audio data from ElevenLabs API.")
        except requests.exceptions.RequestException as error:
            logging.error(f"An error occurred with the ElevenLabs API. Error: {error}")
            return jsonify({"error": "Failed to generate audio from the text response."}), 500

        # --- STEP C: Prepare and send the final response to the frontend ---
        # Encode audio data in Base64 to safely send it within a JSON object.
        audio_base64 = base64.b64encode(audio_response.content).decode('utf-8')

        logging.info("Successfully processed the chat request. Sending text and audio back to the frontend.")
        return jsonify({
            "textResponse": ai_text_response,
            "audioBase64": audio_base64
        })

    except Exception as error:
        # A general catch-all for any other unexpected errors in this function.
        logging.error(f"An unexpected error occurred in the chat handler. Error: {error}", exc_info=True)
        return jsonify({"error": "An unexpected server error occurred. Please check the logs."}), 500

# ==============================================================================
# This block is for local development only. When deployed on Render,
# Gunicorn will be used to run the application, and this block will not be executed.
if __name__ == '__main__':
    # Runs the Flask app on a local server for testing.
    # host='0.0.0.0' makes it accessible on your local network.
    app.run(host='0.0.0.0', port=8080, debug=True)
# ==============================================================================
