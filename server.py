import os
import json
import requests
from flask import Flask, jsonify, send_from_directory

app = Flask(__name__)

# Replace with your actual standard (secret) OpenAI API key
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "YOUR_OPENAI_API_KEY_HERE")


@app.route("/session")
def get_ephemeral_session():
    """
    Endpoint to mint an ephemeral API key for the client.
    The client can call this endpoint to retrieve a short-lived key,
    which can then be used to authenticate with the Realtime API.
    """
    # POST to the Realtime sessions endpoint
    url = "https://api.openai.com/v1/realtime/sessions"
    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/json",
    }
    body = {
        "model": "gpt-4o-mini-realtime-preview-2024-12-17",
        "voice": "verse",  # For example, if you want the model to respond with audio
        "instructions": """You are an empathetic AI therapist. Your role is to:
1. Listen actively and respond with understanding
2. Ask open-ended questions to explore feelings and thoughts
3. Maintain professional boundaries while being warm and supportive
4. Never give medical advice or diagnose conditions
5. Recognize and respond appropriately to crisis situations
6. Use therapeutic techniques like reflection and validation""",
        "tools": [{
            "type": "function",
            "name": "detect_crisis",
            "description": "Analyze input for signs of crisis or emergency situations",
            "parameters": {
                "type": "object",
                "properties": {
                    "crisis_level": {
                        "type": "string",
                        "enum": ["none", "low", "medium", "high", "emergency"],
                        "description": "The assessed level of crisis"
                    },
                    "reason": {
                        "type": "string",
                        "description": "Brief explanation of the crisis assessment"
                    }
                },
                "required": ["crisis_level", "reason"]
            }
        }]
    }

    response = requests.post(url, headers=headers, json=body)

    if response.status_code != 200:
        return jsonify({"error": "Failed to create ephemeral session", "details": response.text}), 400

    data = response.json()
    return jsonify(data)


@app.route("/")
def serve_index():
    """
    Serve the test HTML page at the root path.
    """
    return send_from_directory(".", "index.html")


if __name__ == "__main__":
    # Make sure you've installed Flask and Requests:
    #   pip install flask requests
    app.run(host="0.0.0.0", port=8000, debug=True)
