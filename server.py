import os
import json
import time
import logging
from datetime import datetime
import requests
from flask import Flask, jsonify, send_from_directory, request
from functools import wraps

app = Flask(__name__)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Replace with your actual standard (secret) OpenAI API key
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "YOUR_OPENAI_API_KEY_HERE")

# Simple in-memory rate limiting and session tracking
RATE_LIMIT = {"window_seconds": 60, "max_requests": 30}
rate_limit_store = {}
active_sessions = {}

def rate_limit(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        ip = request.remote_addr
        current_time = time.time()
        
        # Clean up old entries
        rate_limit_store[ip] = [t for t in rate_limit_store.get(ip, [])
                               if current_time - t < RATE_LIMIT["window_seconds"]]
        
        if len(rate_limit_store.get(ip, [])) >= RATE_LIMIT["max_requests"]:
            return jsonify({"error": "Rate limit exceeded"}), 429
        
        rate_limit_store.setdefault(ip, []).append(current_time)
        return f(*args, **kwargs)
    return decorated_function

@app.route("/session")
@rate_limit
def get_ephemeral_session():
    """
    Endpoint to mint an ephemeral API key for the client.
    The client can call this endpoint to retrieve a short-lived key,
    which can then be used to authenticate with the Realtime API.
    """
    try:
        # Generate session ID
        session_id = str(int(time.time() * 1000))
        
        # POST to the Realtime sessions endpoint
        url = "https://api.openai.com/v1/realtime/sessions"
        headers = {
            "Authorization": f"Bearer {OPENAI_API_KEY}",
            "Content-Type": "application/json",
        }
        body = {
            "model": "gpt-4o-mini-realtime-preview-2024-12-17",
            "voice": "verse",
            "instructions": """You are an empathetic AI therapist. Your role is to:
1. Listen actively and respond with understanding
2. Ask open-ended questions to explore feelings and thoughts
3. Maintain professional boundaries while being warm and supportive
4. Never give medical advice or diagnose conditions
5. Recognize and respond appropriately to crisis situations
6. Use therapeutic techniques like reflection and validation
7. Maintain context of the conversation and refer back to previous points when relevant
8. Help clients develop insights and coping strategies
9. End sessions with a clear summary and support plan""",
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
        response.raise_for_status()
        data = response.json()
        
        # Store session info with the client secret
        active_sessions[session_id] = {
            "started_at": datetime.utcnow().isoformat(),
            "last_activity": datetime.utcnow().isoformat(),
            "crisis_events": [],
            "client_secret": data["client_secret"]["value"]  # Store the client secret for session termination
        }
        
        data["session_id"] = session_id
        return jsonify(data)

    except requests.exceptions.RequestException as e:
        logger.error(f"OpenAI API error: {str(e)}")
        return jsonify({"error": "Failed to create ephemeral session", "details": str(e)}), 500
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        return jsonify({"error": "Internal server error"}), 500

@app.route("/session/<session_id>/end", methods=["POST"])
@rate_limit
def end_session(session_id):
    """
    Endpoint to properly terminate a therapy session.
    """
    try:
        session = active_sessions.get(session_id)
        if not session:
            return jsonify({"error": "Session not found"}), 404

        # Since the OpenAI Realtime API doesn't support explicit session termination,
        # we'll just clean up our local session tracking
        session_summary = {
            "session_start": session["started_at"],
            "session_end": datetime.utcnow().isoformat(),
            "crisis_events": session["crisis_events"]
        }
        
        del active_sessions[session_id]
        
        return jsonify({
            "message": "Session terminated successfully",
            "summary": session_summary
        })

    except Exception as e:
        logger.error(f"Error during session termination: {str(e)}")
        return jsonify({"error": "Internal server error"}), 500

@app.route("/session/<session_id>/summary")
@rate_limit
def get_session_summary(session_id):
    """
    Get a summary of the therapy session including duration and crisis events.
    """
    session = active_sessions.get(session_id)
    if not session:
        return jsonify({"error": "Session not found"}), 404
    
    return jsonify({
        "session_start": session["started_at"],
        "last_activity": session["last_activity"],
        "crisis_events": session["crisis_events"]
    })

@app.route("/")
def serve_index():
    """
    Serve the test HTML page at the root path.
    """
    return send_from_directory(".", "index.html")

# Cleanup old sessions periodically
def cleanup_old_sessions():
    current_time = datetime.utcnow()
    for session_id in list(active_sessions.keys()):
        last_activity = datetime.fromisoformat(active_sessions[session_id]["last_activity"])
        if (current_time - last_activity).total_seconds() > 3600:  # 1 hour timeout
            try:
                # Just remove the session from our tracking
                del active_sessions[session_id]
            except Exception as e:
                logger.error(f"Failed to cleanup session {session_id}: {str(e)}")

if __name__ == "__main__":
    # Make sure you've installed Flask and Requests:
    #   pip install flask requests
    app.run(host="0.0.0.0", port=8000, debug=True)
