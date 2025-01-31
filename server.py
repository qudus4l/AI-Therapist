import os
import json
import time
import logging
import secrets
from datetime import datetime, timedelta
import requests
from flask import Flask, jsonify, send_from_directory, request, session, redirect, url_for
from functools import wraps
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", secrets.token_hex(32))

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Replace with your actual standard (secret) OpenAI API key
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "YOUR_OPENAI_API_KEY_HERE")

# Simple in-memory rate limiting and session tracking
RATE_LIMIT = {"window_seconds": 60, "max_requests": 30}
rate_limit_store = {}
active_sessions = {}

# Database setup
def init_db():
    with sqlite3.connect('therapy.db') as conn:
        c = conn.cursor()
        # Users table
        c.execute('''CREATE TABLE IF NOT EXISTS users
                    (id INTEGER PRIMARY KEY AUTOINCREMENT,
                     email TEXT UNIQUE NOT NULL,
                     password_hash TEXT NOT NULL,
                     created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
        
        # Sessions table for therapy sessions
        c.execute('''CREATE TABLE IF NOT EXISTS therapy_sessions
                    (id INTEGER PRIMARY KEY AUTOINCREMENT,
                     user_id INTEGER,
                     started_at TIMESTAMP,
                     ended_at TIMESTAMP,
                     crisis_events TEXT,
                     FOREIGN KEY (user_id) REFERENCES users (id))''')
        conn.commit()

init_db()

# Authentication decorator
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return jsonify({"error": "Authentication required"}), 401
        return f(*args, **kwargs)
    return decorated_function

# Auth routes
@app.route("/auth/login", methods=["POST"])
def login():
    data = request.get_json()
    email = data.get('email')
    password = data.get('password')
    
    if not email or not password:
        return jsonify({"errors": {"email": "Email and password are required"}}), 400
    
    try:
        with sqlite3.connect('therapy.db') as conn:
            c = conn.cursor()
            c.execute("SELECT id, password_hash FROM users WHERE email = ?", (email,))
            user = c.fetchone()
            
            if user and check_password_hash(user[1], password):
                session['user_id'] = user[0]
                return jsonify({"message": "Login successful"})
            else:
                return jsonify({"errors": {"email": "Invalid email or password"}}), 401
    except Exception as e:
        logger.error(f"Login error: {str(e)}")
        return jsonify({"error": "Internal server error"}), 500

@app.route("/auth/signup", methods=["POST"])
def signup():
    data = request.get_json()
    email = data.get('email')
    password = data.get('password')
    
    if not email or not password:
        return jsonify({"errors": {"email": "Email and password are required"}}), 400
    
    try:
        with sqlite3.connect('therapy.db') as conn:
            c = conn.cursor()
            # Check if user exists
            c.execute("SELECT id FROM users WHERE email = ?", (email,))
            if c.fetchone():
                return jsonify({"errors": {"email": "Email already registered"}}), 400
            
            # Create new user
            password_hash = generate_password_hash(password)
            c.execute("INSERT INTO users (email, password_hash) VALUES (?, ?)",
                     (email, password_hash))
            conn.commit()
            
            # Log them in
            user_id = c.lastrowid
            session['user_id'] = user_id
            return jsonify({"message": "Signup successful"})
    except Exception as e:
        logger.error(f"Signup error: {str(e)}")
        return jsonify({"error": "Internal server error"}), 500

@app.route("/auth/logout")
def logout():
    session.clear()
    return jsonify({"message": "Logged out successfully"})

# Serve static files
@app.route("/login")
def serve_login():
    if 'user_id' in session:
        return redirect(url_for('serve_index'))
    return send_from_directory(".", "login.html")

@app.route("/signup")
def serve_signup():
    if 'user_id' in session:
        return redirect(url_for('serve_index'))
    return send_from_directory(".", "signup.html")

@app.route("/profile")
@login_required
def serve_profile():
    return send_from_directory(".", "profile.html")

@app.route("/")
def serve_index():
    if 'user_id' not in session:
        return redirect(url_for('serve_login'))
    return send_from_directory(".", "index.html")

# Existing routes with authentication added
@app.route("/session")
@login_required
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
        
        # Store session info with the client secret and user_id
        active_sessions[session_id] = {
            "user_id": session['user_id'],
            "started_at": datetime.utcnow().isoformat(),
            "last_activity": datetime.utcnow().isoformat(),
            "crisis_events": [],
            "client_secret": data["client_secret"]["value"]
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
@login_required
def end_session(session_id):
    """
    Endpoint to properly terminate a therapy session.
    """
    try:
        session_data = active_sessions.get(session_id)
        if not session_data:
            return jsonify({"error": "Session not found"}), 404

        # Verify user owns this session
        if session_data["user_id"] != session['user_id']:
            return jsonify({"error": "Unauthorized"}), 403

        # Store session in database
        with sqlite3.connect('therapy.db') as conn:
            c = conn.cursor()
            c.execute("""INSERT INTO therapy_sessions 
                        (user_id, started_at, ended_at, crisis_events)
                        VALUES (?, ?, ?, ?)""",
                     (session['user_id'],
                      session_data["started_at"],
                      datetime.utcnow().isoformat(),
                      json.dumps(session_data["crisis_events"])))
            conn.commit()

        # Create session summary
        session_summary = {
            "session_start": session_data["started_at"],
            "session_end": datetime.utcnow().isoformat(),
            "crisis_events": session_data["crisis_events"]
        }
        
        del active_sessions[session_id]
        
        return jsonify({
            "message": "Session terminated successfully",
            "summary": session_summary
        })

    except Exception as e:
        logger.error(f"Error during session termination: {str(e)}")
        return jsonify({"error": "Internal server error"}), 500

@app.route("/user/sessions")
@login_required
def get_user_sessions():
    """
    Get a user's therapy session history
    """
    try:
        with sqlite3.connect('therapy.db') as conn:
            c = conn.cursor()
            c.execute("""SELECT started_at, ended_at, crisis_events 
                        FROM therapy_sessions 
                        WHERE user_id = ? 
                        ORDER BY started_at DESC""",
                     (session['user_id'],))
            sessions = c.fetchall()
            
            return jsonify([{
                "started_at": s[0],
                "ended_at": s[1],
                "crisis_events": json.loads(s[2])
            } for s in sessions])
    except Exception as e:
        logger.error(f"Error fetching user sessions: {str(e)}")
        return jsonify({"error": "Internal server error"}), 500

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
    # Make sure you've installed required packages:
    #   pip install flask requests werkzeug
    app.run(host="0.0.0.0", port=8000, debug=True)
