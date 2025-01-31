# OpenAI Realtime API WebRTC Client

This is a Python implementation of a WebRTC client for OpenAI's Realtime API, which enables real-time speech-to-speech conversations.

## Prerequisites

- Python 3.11
- FFmpeg (installed via Homebrew on macOS)
- OpenAI API key

## Installation

1. Install system dependencies (macOS):
```bash
brew install ffmpeg pkg-config
```

2. Create a Python virtual environment and activate it:
```bash
python3.11 -m venv venv311
source venv311/bin/activate
```

3. Install Python dependencies:
```bash
pip install -r requirements.txt
```

4. Create a `.env` file in the project root and add your OpenAI API key:
```
OPENAI_API_KEY=your_api_key_here
```

## Usage

1. Run the client:
```bash
python realtime_client.py
```

The client will:
- Establish a WebRTC connection with OpenAI's Realtime API
- Set up audio input from your microphone
- Create a data channel for sending and receiving events
- Start a conversation about artificial intelligence

## Features

- Real-time audio streaming using WebRTC
- Secure authentication using ephemeral tokens
- Bidirectional communication through data channel
- Support for both text and speech modalities

## Implementation Details

The implementation consists of two main components:

1. `RealtimeClient` class:
   - Handles WebRTC connection setup
   - Manages audio streaming
   - Handles data channel communication
   - Provides methods for sending events and receiving responses

2. Audio handling:
   - Uses `aiortc` for WebRTC implementation
   - Configures audio input using `MediaPlayer`
   - Supports 48kHz sampling rate and mono channel

## Notes

- The current implementation uses the `avfoundation` format for audio input on macOS
- Make sure your microphone is properly configured and accessible
- The connection will remain active until you interrupt the program (Ctrl+C)

## Error Handling

If you encounter any issues:
1. Check that your OpenAI API key is valid and properly set in the `.env` file
2. Ensure your microphone is working and accessible
3. Verify that all dependencies are properly installed
4. Check your internet connection 