# main.py
from flask import Flask, Response, request, send_from_directory
from flask_socketio import SocketIO, emit, join_room, leave_room
import os
import datetime
import json
import re
import shutil # For clearing uploads directory

app = Flask(__name__)

# --- Configuration for Production ---
# Use environment variables for sensitive data and dynamic configurations
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'a_very_secret_and_long_key_for_as_chat_app_by_your_name_CHANGE_THIS_IN_PROD')
# It's crucial to set this to a strong, unique value in your production environment variables.

# Host password should also be from environment variable for security
HOST_PASSWORD = os.environ.get('HOST_PASSWORD', 'my_secret_host_key_CHANGE_THIS_FOR_PRODUCTION!') 
# IMPORTANT: Never use 'my_secret_host_key_CHANGE_THIS_FOR_PRODUCTION!' in production.
# Set a strong, unique password via your hosting platform's environment variables.

# Adjust SocketIO for production deployment (e.g., eventlet/gevent, message queues)
# For simple deployments, you might not need an explicit message_queue if sticky sessions are supported.
# For scaled deployments, a message queue (like Redis) is essential.
# Example with Redis:
# socketio = SocketIO(app, message_queue=os.environ.get('REDIS_URL', 'redis://localhost:6379/0'))
socketio = SocketIO(app) # For basic deployment without explicit message queue config

CHAT_ROOM = "main_as_chat_room"

hosts = set() # Stores session IDs of current hosts
muted_users = set() # Stores session IDs of individual muted users
chat_disabled_for_all = False # New flag to disable chat for everyone (except host)

# Stores user information (sid: {username, is_host, is_muted})
user_info = {}

# --- Video Sharing Setup ---
# Use an absolute path for UPLOAD_FOLDER for better compatibility across different hosting environments.
# Ensure your hosting platform allows writing to this directory and it persists across restarts if needed.
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, 'uploads')

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

# To store the path of the currently shared video on the server
current_shared_video_server_path = None

# --- Frontend HTML, CSS, JavaScript as Python strings ---
# It's generally better practice to serve these from static files (e.g., a 'static' folder)
# in production, letting the web server (Nginx, Apache) handle them efficiently.
# However, for a single-file Flask app, keeping them as strings is acceptable for small scale.

CSS_CONTENT = """
/* General Styling */
:root {
    --primary-blue: #007BFF;       /* Vibrant Blue */
    --dark-blue: #0056b3;          /* Darker Blue for accents/hover */
    --light-blue: #EBF5FB;         /* Very light blue for subtle backgrounds */
    --silver-light: #F0F2F5;       /* Lightest silver/off-white for background */
    --silver-medium: #CCCCCC;      /* Medium silver for borders/dividers */
    --silver-dark: #A0A0A0;        /* Darker silver for shadows/text contrast */
    --text-color-dark: #333333;    /* Dark grey for main text */
    --text-color-light: #666666;   /* Lighter grey for secondary text */
    --white: #FFFFFF;
    --black: #000000;
    --error-red: #DC3545;
    --success-green: #28A745;
    --warning-orange: #FFC107;
    --info-color: #17a2b8; /* A standard info blue */

    --border-radius-soft: 8px;
    --border-radius-round: 25px;
    --box-shadow-light: 0 4px 15px rgba(0, 0, 0, 0.1);
    --transition-speed: 0.3s ease;
}

* {
    box-sizing: border-box;
    margin: 0;
    padding: 0;
}

body {
    font-family: 'Roboto', sans-serif;
    margin: 0;
    padding: 0;
    background: linear-gradient(to right, var(--silver-light), var(--light-blue));
    color: var(--text-color-dark);
    display: flex; /* Use flexbox to center content */
    justify-content: center; /* Center horizontally */
    align-items: center; /* Center vertically */
    min-height: 100vh; /* Full viewport height */
    font-size: 16px;
    line-height: 1.6;
    overflow-x: hidden; /* Prevent horizontal scroll */
    padding: 10px; /* Small padding for very small screens */
}

.container {
    background-color: var(--white);
    border-radius: var(--border-radius-soft);
    box-shadow: var(--box-shadow-light);
    width: 95%; /* Make it take most of the width on mobile */
    max-width: 1400px; /* Max width for larger screens */
    display: flex;
    flex-direction: column;
    overflow: hidden;
    min-height: 90vh; /* Allow it to take up most of the vertical space */
    margin: auto; /* Center the container if it's smaller than min-height */
}

/* Header */
header {
    background-color: var(--primary-blue);
    color: var(--white);
    padding: 20px 15px; /* Slightly reduced padding for mobile */
    text-align: center;
    border-bottom: 5px solid var(--dark-blue);
    box-shadow: 0 2px 8px rgba(0,0,0,0.15);
    position: relative;
}

.logo {
    font-size: 2.5em; /* Smaller logo for mobile */
    font-weight: bold;
    margin-bottom: 5px;
    letter-spacing: 1px; /* Slightly reduced letter spacing */
    text-shadow: 1px 1px 2px rgba(0,0,0,0.3);
}

h1 {
    color: var(--white);
    margin-top: 5px;
    font-size: 1.5em; /* Smaller H1 for mobile */
}

h2, h3, h4 {
    color: var(--dark-blue);
    margin-top: 0;
    margin-bottom: 15px;
    font-weight: 600;
}

h2 { font-size: 1.6em; } /* Adjusted h2 size */
h3 { font-size: 1.2em; } /* Adjusted h3 size */
h4 { font-size: 1em; color: var(--text-color-light); } /* Adjusted h4 size */


/* Main Content Layout - Mobile First */
.main-content {
    display: flex;
    flex-direction: column; /* Stack panels vertically by default */
    padding: 15px; /* Reduced padding */
    gap: 15px; /* Reduced gap */
    flex-grow: 1;
    overflow-y: auto; /* Allow scrolling if content overflows */
}

.video-panel, .chat-panel {
    background-color: var(--silver-light);
    border-radius: var(--border-radius-soft);
    padding: 15px; /* Reduced padding */
    box-shadow: inset 0 1px 8px rgba(0,0,0,0.08);
    display: flex;
    flex-direction: column;
}

.video-panel {
    flex-grow: 1; /* Allow video panel to grow */
}

.chat-panel {
    flex-grow: 1; /* Allow chat panel to grow */
}


/* Video Player */
.video-container {
    position: relative;
    width: 100%;
    padding-top: 56.25%; /* 16:9 Aspect Ratio */
    background-color: var(--black);
    border-radius: var(--border-radius-soft);
    overflow: hidden;
    margin-bottom: 10px; /* Reduced margin */
    border: 1px solid var(--silver-medium);
}

.video-container video {
    position: absolute;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
    object-fit: contain;
    background-color: var(--black);
}

.video-placeholder {
    position: absolute;
    top: 50%;
    left: 50%;
    transform: translate(-50%, -50%);
    color: var(--silver-dark);
    font-style: italic;
    font-size: 1em; /* Smaller font size */
    text-align: center;
    text-shadow: 1px 1px 2px rgba(0,0,0,0.4);
}

/* Chat Box */
.message-box {
    border: 1px solid var(--silver-medium);
    border-radius: var(--border-radius-soft);
    height: 300px; /* Reduced fixed height for mobile */
    overflow-y: auto;
    padding: 10px; /* Reduced padding */
    background-color: var(--white);
    margin-bottom: 10px; /* Reduced margin */
    display: flex;
    flex-direction: column;
    gap: 8px; /* Reduced gap between messages */
    box-shadow: inset 0 1px 5px rgba(0,0,0,0.05);
}

.message {
    background-color: var(--light-blue);
    padding: 8px 12px; /* Reduced padding */
    border-radius: var(--border-radius-round);
    max-width: 90%; /* Slightly increased max-width for mobile */
    align-self: flex-start;
    word-wrap: break-word;
    box-shadow: 0 1px 4px rgba(0,0,0,0.08);
    transition: transform 0.2s ease;
    font-size: 0.9em; /* Smaller font size for messages */
}

.message.system {
    background-color: var(--silver-medium);
    color: var(--white);
    text-align: center;
    font-style: italic;
    max-width: 100%;
    align-self: center;
    padding: 6px 10px; /* Reduced padding */
    border-radius: var(--border-radius-soft);
    box-shadow: none;
    font-size: 0.85em; /* Smaller font for system messages */
}

.message.error {
    background-color: var(--error-red);
    color: var(--white);
    text-align: center;
    font-weight: bold;
    padding: 6px 10px; /* Reduced padding */
    border-radius: var(--border-radius-soft);
    font-size: 0.85em; /* Smaller font for error messages */
}

.message .username {
    font-weight: bold;
    color: var(--dark-blue);
    margin-bottom: 2px; /* Reduced margin */
    display: block;
    font-size: 0.8em; /* Smaller font for username */
}

.message-box .my-sid-display {
    text-align: center;
    font-size: 0.75em; /* Smaller font for SID */
    color: var(--text-color-light);
    margin-bottom: 10px;
    padding: 5px;
    border-bottom: 1px dashed var(--silver-medium);
}

/* Form Controls */
.input-area, .host-auth-area, .host-controls-section, .user-mute-controls {
    display: flex;
    flex-direction: column; /* Stack inputs/buttons vertically by default */
    gap: 10px; /* Reduced gap */
    margin-top: 10px;
    flex-wrap: wrap;
    align-items: stretch; /* Stretch items to full width */
}

.text-input, .file-input {
    width: 100%; /* Full width by default */
    padding: 10px 15px; /* Reduced padding */
    border: 1px solid var(--silver-medium);
    border-radius: var(--border-radius-round);
    font-size: 1em;
    background-color: var(--white);
    outline: none;
    transition: all var(--transition-speed);
    box-shadow: inset 0 1px 3px rgba(0,0,0,0.05);
}

.text-input:focus, .file-input:focus {
    border-color: var(--primary-blue);
    box-shadow: 0 0 0 3px rgba(0, 123, 255, 0.25);
}

.btn {
    width: 100%; /* Full width by default */
    padding: 10px 20px; /* Reduced padding */
    border: none;
    border-radius: var(--border-radius-round);
    cursor: pointer;
    font-size: 1em;
    font-weight: bold;
    transition: background-color var(--transition-speed), transform 0.2s ease;
    white-space: nowrap;
    text-transform: uppercase;
    letter-spacing: 0.5px;
}

.btn-primary { background-color: var(--primary-blue); color: var(--white); }
.btn-primary:hover { background-color: var(--dark-blue); transform: translateY(-2px); box-shadow: 0 4px 8px rgba(0, 123, 255, 0.3); }

.btn-secondary { background-color: var(--silver-dark); color: var(--white); }
.btn-secondary:hover { background-color: var(--silver-medium); transform: translateY(-2px); box-shadow: 0 4px 8px rgba(160, 160, 160, 0.3); }

.btn-danger { background-color: var(--error-red); color: var(--white); }
.btn-danger:hover { background-color: #c82333; transform: translateY(-2px); box-shadow: 0 4px 8px rgba(220, 53, 69, 0.3); } /* Adjusted hover for red */

.btn-warning { background-color: var(--warning-orange); color: var(--text-color-dark); }
.btn-warning:hover { background-color: #e0a800; transform: translateY(-2px); box-shadow: 0 4px 8px rgba(255, 193, 7, 0.3); } /* Adjusted hover for warning */

.btn-info { background-color: var(--info-color); color: var(--white); }
.btn-info:hover { background-color: #138496; transform: translateY(-2px); } /* Adjusted hover for info */


/* Host specific styles */
.host-controls-section {
    border-top: 1px dashed var(--silver-medium);
    padding-top: 15px;
    margin-top: 20px;
    flex-direction: column;
    align-items: stretch;
}

.host-controls-section h3, .host-controls-section h4 {
    margin-bottom: 10px;
    text-align: center;
}

.user-mute-controls {
    flex-direction: column;
    margin-top: 10px;
    padding: 15px;
    background-color: var(--white);
    border-radius: var(--border-radius-soft);
    box-shadow: inset 0 1px 3px rgba(0,0,0,0.05);
}

.user-list {
    list-style: none;
    padding: 0;
    max-height: 150px;
    overflow-y: auto;
    border: 1px solid var(--silver-medium);
    border-radius: var(--border-radius-soft);
    margin-bottom: 10px;
    background-color: var(--silver-light);
}

.user-list li {
    padding: 8px 12px;
    border-bottom: 1px solid var(--silver-light);
    font-size: 0.9em;
    color: var(--text-color-dark);
}

.user-list li:last-child {
    border-bottom: none;
}

/* Feedback messages */
.feedback-message {
    padding: 10px;
    border-radius: 5px;
    margin-top: 10px;
    text-align: center;
    font-weight: bold;
    opacity: 1;
    transition: opacity 0.5s ease-out;
}

.feedback-message.success {
    background-color: var(--success-green);
    color: var(--white);
}

.feedback-message.error {
    background-color: var(--error-red);
    color: var(--white);
}

/* Media Queries for Larger Screens (Tablet and Desktop) */
@media (min-width: 768px) {
    .container {
        width: 90%; /* Slightly wider on tablets */
        min-height: 85vh; /* Adapt height for larger screens */
    }

    header {
        padding: 25px 20px;
    }

    .logo {
        font-size: 3em;
        letter-spacing: 2px;
    }

    h1 {
        font-size: 1.8em;
    }

    h2 { font-size: 1.8em; }
    h3 { font-size: 1.4em; }
    h4 { font-size: 1.1em; }

    .main-content {
        flex-direction: row; /* Layout panels side-by-side on larger screens */
        padding: 25px;
        gap: 25px;
    }

    .video-panel, .chat-panel {
        flex: 1; /* Distribute space equally */
        min-width: 380px; /* Minimum width for panels */
        padding: 20px;
    }

    .video-panel {
        flex-grow: 2; /* Video panel takes more space */
    }

    .chat-panel {
        flex-grow: 1;
    }

    .message-box {
        height: 400px; /* Taller message box on larger screens */
        padding: 15px;
        gap: 10px;
    }

    .message {
        padding: 10px 15px;
        font-size: 1em;
        max-width: 85%;
    }
    .message.system, .message.error {
        padding: 8px 12px;
        font-size: 0.9em;
    }
    .message .username {
        font-size: 0.9em;
    }

    .video-placeholder {
        font-size: 1.2em;
    }

    .input-area, .host-auth-area {
        flex-direction: row; /* Arrange horizontally on larger screens */
        gap: 10px;
    }
    .text-input, .file-input {
        width: auto; /* Allow them to shrink/grow based on content */
    }
    .btn {
        width: auto; /* Allow buttons to shrink/grow based on content */
    }

    .host-controls-section, .user-mute-controls {
        flex-direction: column; /* Keep stacked for controls clarity */
    }
}

/* Specific adjustments for very small screens (e.g., old phones) */
@media (max-width: 480px) {
    body {
        padding: 5px;
    }
    .container {
        width: 100%;
        min-height: 95vh;
        margin: 0; /* Remove margin to use full width */
        border-radius: 0; /* No border radius on very small screens for full coverage */
        box-shadow: none; /* No shadow */
    }
    header {
        padding: 15px 10px;
        border-radius: 0;
    }
    .logo {
        font-size: 2em;
    }
    h1 {
        font-size: 1.3em;
    }
    .main-content {
        padding: 10px;
        gap: 10px;
    }
    .video-panel, .chat-panel {
        padding: 10px;
    }
    .message-box {
        height: 250px; /* Even smaller message box on very small screens */
        padding: 8px;
        gap: 5px;
    }
    .message {
        padding: 6px 10px;
        font-size: 0.85em;
    }
    .message.system, .message.error {
        padding: 5px 8px;
        font-size: 0.8em;
    }
    .message .username {
        font-size: 0.75em;
    }
    .text-input, .file-input, .btn {
        font-size: 0.9em;
        padding: 8px 12px;
    }
}
"""

JS_CONTENT = """
const socket = io();

const messagesDiv = document.getElementById('messages');
const usernameInput = document.getElementById('usernameInput');
const messageInput = document.getElementById('messageInput');
const sendMessageBtn = document.getElementById('sendMessage');
const sharedVideo = document.getElementById('sharedVideo');
const videoFileInput = document.getElementById('videoFileInput');
const startVideoShareBtn = document.getElementById('startVideoShare');
const clearSharedVideoBtn = document.getElementById('clearSharedVideo');
const hostPasswordInput = document.getElementById('hostPasswordInput');
const authenticateHostBtn = document.getElementById('authenticateHost');
const hostAuthFeedback = document.getElementById('hostAuthFeedback');
const hostVideoControlsDiv = document.getElementById('hostVideoControls');
const hostChatControlsDiv = document.getElementById('hostChatControls');
const muteUserIdInput = document.getElementById('muteUserId');
const toggleMuteBtn = document.getElementById('toggleMute');
const toggleChatEnabledBtn = document.getElementById('toggleChatEnabled');
const connectedUsersList = document.getElementById('connectedUsersList');
const videoContainer = document.getElementById('videoContainer');
const noVideoMessage = document.getElementById('noVideoMessage');

let isHost = false;
let isChatEnabled = true;

// --- Helper Functions ---
function addMessage(data, type = 'user') {
    const messageElement = document.createElement('div');
    messageElement.classList.add('message');
    if (type === 'system') {
        messageElement.classList.add('system');
        messageElement.textContent = data.msg;
    } else if (type === 'error') {
        messageElement.classList.add('error');
        messageElement.textContent = data.msg;
    } else {
        const usernameSpan = document.createElement('span');
        usernameSpan.classList.add('username');
        usernameSpan.textContent = data.username;
        messageElement.appendChild(usernameSpan);
        messageElement.appendChild(document.createTextNode(data.message));
    }
    messagesDiv.appendChild(messageElement);
    messagesDiv.scrollTop = messagesDiv.scrollHeight;
}

function showFeedback(message, type) {
    hostAuthFeedback.textContent = message;
    hostAuthFeedback.className = 'feedback-message ' + type;
    hostAuthFeedback.style.display = 'block';
    setTimeout(() => {
        hostAuthFeedback.style.opacity = '0';
        setTimeout(() => {
            hostAuthFeedback.style.display = 'none';
            hostAuthFeedback.style.opacity = '1';
        }, 500);
    }, 2000);
}

function updateConnectedUsersList(users) {
    connectedUsersList.innerHTML = '';
    for (const sid in users) {
        const userInfo = users[sid];
        const listItem = document.createElement('li');
        let status = '';
        if (userInfo.is_host) status += ' (Host)';
        if (userInfo.is_muted) status += ' (Muted)';
        listItem.textContent = `${sid}: ${userInfo.username}${status}`;
        connectedUsersList.appendChild(listItem);
    }
}

function toggleChatInput(enabled) {
    messageInput.disabled = !enabled;
    sendMessageBtn.disabled = !enabled;
    if (enabled) {
        messageInput.placeholder = "Type your message...";
    } else {
        messageInput.placeholder = "Chat is currently disabled by the host.";
    }
}

// --- Event Listeners ---
sendMessageBtn.addEventListener('click', () => {
    const username = usernameInput.value || 'Anonymous';
    const message = messageInput.value;
    if (message.trim()) {
        socket.emit('message', { username, message });
        messageInput.value = '';
    }
});

messageInput.addEventListener('keypress', (e) => {
    if (e.key === 'Enter') {
        sendMessageBtn.click();
    }
});

authenticateHostBtn.addEventListener('click', () => {
    const password = hostPasswordInput.value;
    socket.emit('authenticate_host', { password });
});

toggleMuteBtn.addEventListener('click', () => {
    const targetSid = muteUserIdInput.value;
    if (targetSid) {
        socket.emit('toggle_mute_user', { target_sid: targetSid });
    } else {
        alert('Please enter a User SID to mute/unmute.');
    }
});

toggleChatEnabledBtn.addEventListener('click', () => {
    socket.emit('toggle_chat_enabled', { enabled: !isChatEnabled });
});

// --- Video Sharing Logic ---
let currentVideoBlobUrl = null;

videoFileInput.addEventListener('change', (event) => {
    if (event.target.files.length > 0) {
        const file = event.target.files[0];
        // Revoke previous blob URL to free up memory
        if (currentVideoBlobUrl) URL.revokeObjectURL(currentVideoBlobUrl);
        currentVideoBlobUrl = URL.createObjectURL(file);
        sharedVideo.src = currentVideoBlobUrl;
        sharedVideo.style.display = 'block';
        noVideoMessage.style.display = 'none';
        sharedVideo.load();
    }
});

startVideoShareBtn.addEventListener('click', () => {
    if (isHost && videoFileInput.files.length > 0) {
        const file = videoFileInput.files[0];
        const formData = new FormData();
        formData.append('video', file);

        addMessage({ msg: 'Uploading video...', type: 'system' });

        // Include SID in the URL for basic authentication check on upload endpoint
        // This is a basic check. For production, consider using proper session management
        // and CSRF tokens if this endpoint were exposed without SocketIO's SID mechanism.
        fetch(`/upload_video?sid=${socket.id}`, {
            method: 'POST',
            body: formData,
        })
        .then(response => {
            if (!response.ok) { // Check for HTTP errors
                return response.json().then(errorData => {
                    throw new Error(errorData.error || 'Server error');
                });
            }
            return response.json();
        })
        .then(data => {
            if (data.success) {
                addMessage({ msg: 'Video uploaded successfully!', type: 'system' });
                socket.emit('host_starts_video_share', { video_url: data.video_url });
            } else {
                addMessage({ msg: 'Video upload failed: ' + data.error, type: 'error' });
            }
        })
        .catch(error => {
            console.error('Error uploading video:', error);
            addMessage({ msg: 'Error uploading video: ' + error.message, type: 'error' });
        });
    } else if (!isHost) {
        alert('Only the host can share videos.');
    } else {
        alert('Please select a video file first.');
    }
});

clearSharedVideoBtn.addEventListener('click', () => {
    if (isHost) {
        socket.emit('host_clears_video');
    } else {
        alert('Only the host can clear shared video.');
    }
});

// Host sending video control commands to synchronize playback
let syncInterval;
sharedVideo.addEventListener('play', () => {
    if (isHost && !syncInterval) {
        socket.emit('host_video_control', { action: 'play', time: sharedVideo.currentTime });
        syncInterval = setInterval(() => {
            if (!sharedVideo.paused) {
                socket.emit('host_video_control', { action: 'seek', time: sharedVideo.currentTime });
            }
        }, 3000); // Sync every 3 seconds
    }
});

sharedVideo.addEventListener('pause', () => {
    if (isHost) {
        socket.emit('host_video_control', { action: 'pause', time: sharedVideo.currentTime });
        if (syncInterval) {
            clearInterval(syncInterval);
            syncInterval = null;
        }
    }
});

sharedVideo.addEventListener('seeked', () => {
    if (isHost) {
        socket.emit('host_video_control', { action: 'seek', time: sharedVideo.currentTime });
    }
});

sharedVideo.addEventListener('ended', () => {
    if (isHost && syncInterval) {
        clearInterval(syncInterval);
        syncInterval = null;
    }
    // Optionally, clear video on host side after it ends
    // socket.emit('host_clears_video'); 
});

// --- Socket.IO Event Handlers ---
socket.on('connect', () => {
    console.log('Connected to server!');
    const mySidElement = document.createElement('p');
    mySidElement.classList.add('my-sid-display');
    mySidElement.textContent = `Your Session ID: ${socket.id}`;
    messagesDiv.prepend(mySidElement); // Add to the top of messages for visibility
    socket.emit('request_initial_state'); // Request initial state on connect
});

socket.on('new_message', (data) => {
    addMessage(data);
});

socket.on('status', (data) => {
    addMessage(data, 'system');
});

socket.on('host_authenticated', (data) => {
    if (data.success) {
        isHost = true;
        hostVideoControlsDiv.style.display = 'flex';
        hostChatControlsDiv.style.display = 'block';
        showFeedback('You are now authenticated as a host!', 'success');
        socket.emit('request_user_list');
        socket.emit('request_initial_state'); // Re-request initial state to get current video/chat status as host
    } else {
        showFeedback('Host authentication failed: ' + data.error, 'error');
    }
});

socket.on('you_are_muted', () => {
    toggleChatInput(false);
    addMessage({ msg: 'You have been muted by the host. You cannot send messages.', type: 'error' });
});

socket.on('you_are_unmuted', () => {
    // Only re-enable chat input if chat is globally enabled
    // The 'update_chat_status' event will handle the global chat status.
    // This just ensures the personal mute status is reflected.
    socket.emit('get_my_user_status', {}, (status_data) => {
        if (isChatEnabled && !status_data.is_muted) {
            toggleChatInput(true);
        }
    });
    addMessage({ msg: 'You have been unmuted by the host. You can now send messages.', type: 'system' });
});


socket.on('update_user_list', (data) => {
    if (isHost) { // Only update if current user is a host
        updateConnectedUsersList(data.users);
    }
});

socket.on('start_video_playback', (data) => {
    if (data.video_url) {
        sharedVideo.src = data.video_url;
        sharedVideo.style.display = 'block';
        noVideoMessage.style.display = 'none';
        sharedVideo.load();
        sharedVideo.play().catch(e => console.error("Video auto-play prevented:", e));
        addMessage({ msg: 'Video playback started by host!', type: 'system' });
    }
});

socket.on('clear_video_playback', () => {
    sharedVideo.pause();
    sharedVideo.src = '';
    sharedVideo.style.display = 'none';
    noVideoMessage.style.display = 'block';
    addMessage({ msg: 'Host has stopped sharing the video.', type: 'system' });
});

socket.on('sync_video_playback', (data) => {
    if (!isHost) { // Only non-hosts should sync
        if (data.action === 'play') {
            sharedVideo.play().catch(e => console.error("Video auto-play prevented:", e));
        } else if (data.action === 'pause') {
            sharedVideo.pause();
        } else if (data.action === 'seek' && data.time !== undefined) {
            // Only seek if difference is significant to avoid constant seeking
            if (Math.abs(sharedVideo.currentTime - data.time) > 1.0) { // Increased threshold slightly
                sharedVideo.currentTime = data.time;
            }
        }
    }
});

socket.on('update_chat_status', (data) => {
    isChatEnabled = data.enabled;
    if (isHost) {
        toggleChatEnabledBtn.textContent = isChatEnabled ? 'Disable Chat for All' : 'Enable Chat for All';
        toggleChatEnabledBtn.className = isChatEnabled ? 'btn btn-warning' : 'btn btn-primary';
    }

    // Determine chat input state based on global chat status and user's mute status
    socket.emit('get_my_user_status', {}, (status_data) => {
        if (status_data.is_host) {
            toggleChatInput(true); // Host can always chat
        } else if (status_data.is_muted) {
            toggleChatInput(false); // Muted users cannot chat
        } else {
            toggleChatInput(isChatEnabled); // Non-muted users follow global chat status
        }

        if (!isHost) { // Only show status message for non-hosts
            if (!isChatEnabled && !status_data.is_muted) { // If chat disabled globally and not personally muted
                addMessage({ msg: 'Chat has been disabled by the host.', type: 'system' });
            } else if (isChatEnabled && !status_data.is_muted) { // If chat enabled globally and not personally muted
                addMessage({ msg: 'Chat has been re-enabled by the host.', type: 'system' });
            }
        }
    });
});

socket.on('initial_state', (data) => {
    isChatEnabled = data.chat_enabled;
    const mySid = socket.id;

    // Request user status to update host controls and chat input correctly
    socket.emit('get_my_user_status', {}, (status_data) => {
        isHost = status_data.is_host; // Update isHost status on initial state
        if (isHost) {
             hostVideoControlsDiv.style.display = 'flex';
             hostChatControlsDiv.style.display = 'block';
             toggleChatEnabledBtn.textContent = isChatEnabled ? 'Disable Chat for All' : 'Enable Chat for All';
             toggleChatEnabledBtn.className = isChatEnabled ? 'btn btn-warning' : 'btn btn-primary';
        } else {
            hostVideoControlsDiv.style.display = 'none';
            hostChatControlsDiv.style.display = 'none';
        }

        // Apply chat input state based on host status, mute status, and global chat status
        if (status_data.is_host) {
            toggleChatInput(true); // Host can always chat
        } else if (status_data.is_muted) {
            toggleChatInput(false); // Muted users cannot chat
        } else {
            toggleChatInput(isChatEnabled); // Non-muted users follow global chat status
        }
    });

    if (data.current_video_url) {
        sharedVideo.src = data.current_video_url;
        sharedVideo.style.display = 'block';
        noVideoMessage.style.display = 'none';
        sharedVideo.load();
        // Don't auto-play on initial load for all, only when initiated by host sync
    } else {
        sharedVideo.style.display = 'none';
        noVideoMessage.style.display = 'block';
    }
});

socket.on('get_my_user_status_response', (data) => {
    // This callback is handled by the socket.emit call, no global listener needed
});
"""

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>As Chat - Group Chat</title>
    <style>{css_content}</style>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/socket.io/4.0.0/socket.io.js"></script>
    <link href="https://fonts.googleapis.com/css2?family=Roboto:wght@300;400;700&display=swap" rel="stylesheet">
</head>
<body>
    <div class="container">
        <header>
            <div class="logo">As Chat</div>
            <h1>Welcome to Group Chat!</h1>
        </header>

        <main class="main-content">
            <div class="video-panel">
                <h2>Shared Video</h2>
                <div id="videoContainer" class="video-container">
                    <video id="sharedVideo" controls autoplay muted style="display:none;"></video>
                    <p id="noVideoMessage" class="video-placeholder">No video is being shared yet.</p>
                </div>
                <div id="hostVideoControls" class="host-controls-section" style="display: none;">
                    <h3>Video Sharing Controls</h3>
                    <input type="file" id="videoFileInput" accept="video/*" class="file-input">
                    <button id="startVideoShare" class="btn btn-primary">Share Video</button>
                    <button id="clearSharedVideo" class="btn btn-danger">Clear Shared Video</button>
                </div>
            </div>

            <div class="chat-panel">
                <h2>Chat Room</h2>
                <div id="messages" class="message-box">
                    </div>
                <div class="input-area">
                    <input type="text" id="usernameInput" placeholder="Your Name" value="Anonymous" class="text-input">
                    <input type="text" id="messageInput" placeholder="Type your message..." autocomplete="off" class="text-input">
                    <button id="sendMessage" class="btn btn-primary">Send</button>
                </div>
                <div class="host-auth-area">
                    <input type="password" id="hostPasswordInput" placeholder="Host Password" class="text-input">
                    <button id="authenticateHost" class="btn btn-secondary">Become Host</button>
                    <div id="hostAuthFeedback" class="feedback-message" style="display:none;"></div>
                </div>
                <div id="hostChatControls" class="host-controls-section" style="display: none;">
                    <h3>Host Chat Controls</h3>
                    <button id="toggleChatEnabled" class="btn btn-warning">Disable Chat for All</button>
                    <div class="user-mute-controls">
                        <h4>Connected Users (SID: Username):</h4>
                        <ul id="connectedUsersList" class="user-list"></ul>
                        <input type="text" id="muteUserId" placeholder="User SID to Mute/Unmute" class="text-input">
                        <button id="toggleMute" class="btn btn-info">Toggle Mute</button>
                    </div>
                </div>
            </div>
        </main>
    </div>

    <script>{js_content}</script>
</body>
</html>
"""

# --- Flask Routes ---

@app.route('/')
def index():
    # Render the HTML template by injecting CSS and JS content
    return HTML_TEMPLATE.format(css_content=CSS_CONTENT, js_content=JS_CONTENT)

# --- WebSocket Event Handlers ---

@socketio.on('connect')
def handle_connect():
    sid = request.sid
    print(f"Client connected: {sid}")
    join_room(CHAT_ROOM)
    # Initialize user_info with default values
    if sid not in user_info:
        user_info[sid] = {'username': 'Anonymous', 'is_host': False, 'is_muted': False}
    
    # Send the initial chat_disabled_for_all status to the new user
    emit('update_chat_status', {'enabled': not chat_disabled_for_all}, room=sid)

    # For hosts, update the user list immediately on connect
    for host_sid in hosts:
        emit('update_user_list', {'users': user_info}, room=host_sid)
    
    # Request initial state will be called by client JS
    
@socketio.on('disconnect')
def handle_disconnect():
    sid = request.sid
    # Check if the user was a host, and if so, remove them from the hosts set
    if sid in hosts:
        hosts.remove(sid)
    
    username = user_info.pop(sid, {}).get('username', f'User {sid[:4]}') # Get username before removing
    print(f"Client disconnected: {sid}")
    
    # Remove from muted_users if they were muted
    if sid in muted_users:
        muted_users.remove(sid)

    # Emit a system message about disconnection
    emit('status', {'msg': f'{username} has disconnected.', 'type': 'system'}, room=CHAT_ROOM)

    # Update user list for remaining hosts
    for host_sid in hosts:
        emit('update_user_list', {'users': user_info}, room=host_sid)


@socketio.on('message')
def handle_message(data):
    sid = request.sid
    username = data.get('username', 'Anonymous')
    message = data.get('message', '')
    
    # Update username in user_info if changed by client
    if sid in user_info:
        user_info[sid]['username'] = username

    is_host = sid in hosts
    is_muted = sid in muted_users

    if not message.strip():
        emit('status', {'msg': 'Message cannot be empty.', 'type': 'error'}, room=sid)
        return

    if chat_disabled_for_all and not is_host:
        emit('status', {'msg': 'Chat is currently disabled by the host.', 'type': 'error'}, room=sid)
        return

    if is_muted and not is_host: 
        emit('status', {'msg': 'You are currently muted and cannot send messages.', 'type': 'error'}, room=sid)
        return

    print(f"Message from {username} ({sid}): {message}")
    emit('new_message', {'username': username, 'message': message}, room=CHAT_ROOM)


@socketio.on('authenticate_host')
def authenticate_host(data):
    sid = request.sid
    password = data.get('password')
    if password == HOST_PASSWORD:
        hosts.add(sid)
        if sid in user_info:
            user_info[sid]['is_host'] = True
        emit('host_authenticated', {'success': True}, room=sid)
        username = user_info.get(sid, {}).get('username', sid)
        emit('status', {'msg': f'User {username} is now a host.', 'type': 'system'}, room=CHAT_ROOM)
        print(f"User {sid} authenticated as host.")
        for host_sid in hosts:
            emit('update_user_list', {'users': user_info}, room=host_sid)
    else:
        emit('host_authenticated', {'success': False, 'error': 'Invalid password'}, room=sid)
        print(f"User {sid} failed host authentication.")

@socketio.on('toggle_mute_user')
def toggle_mute_user(data):
    sid = request.sid
    if sid not in hosts:
        emit('status', {'msg': 'Permission denied: Only hosts can mute users.', 'type': 'error'}, room=sid)
        return

    target_sid = data.get('target_sid')
    if target_sid in user_info and target_sid != sid: # Cannot mute self
        target_username = user_info[target_sid]['username']
        if target_sid in hosts: # Prevent muting other hosts
            emit('status', {'msg': f'Cannot mute host "{target_username}".', 'type': 'error'}, room=sid)
            return

        if target_sid in muted_users:
            muted_users.remove(target_sid)
            user_info[target_sid]['is_muted'] = False
            emit('status', {'msg': f'User {target_username} has been unmuted by host.', 'type': 'system'}, room=CHAT_ROOM)
            emit('you_are_unmuted', room=target_sid)
            print(f"User {target_sid} unmuted by host {user_info.get(sid,{}).get('username',sid)}.")
        else:
            muted_users.add(target_sid)
            user_info[target_sid]['is_muted'] = True
            emit('status', {'msg': f'User {target_username} has been muted by host.', 'type': 'system'}, room=CHAT_ROOM)
            emit('you_are_muted', room=target_sid)
            print(f"User {target_sid} muted by host {user_info.get(sid,{}).get('username',sid)}.")
        
        for host_sid in hosts:
            emit('update_user_list', {'users': user_info}, room=host_sid)
    elif target_sid == sid:
        emit('status', {'msg': 'You cannot mute yourself.', 'type': 'error'}, room=sid)
    else:
        emit('status', {'msg': f'User {target_sid} not found or invalid.', 'type': 'error'}, room=sid)

@socketio.on('request_user_list')
def request_user_list():
    sid = request.sid
    if sid in hosts:
        emit('update_user_list', {'users': user_info}, room=sid)

@socketio.on('toggle_chat_enabled')
def toggle_chat_enabled(data):
    sid = request.sid
    global chat_disabled_for_all
    if sid not in hosts:
        emit('status', {'msg': 'Permission denied: Only hosts can toggle chat.', 'type': 'error'}, room=sid)
        return
    
    # Data.get('enabled') reflects the *new* state (true for enabled, false for disabled)
    new_chat_status = data.get('enabled') 
    chat_disabled_for_all = not new_chat_status # Invert because our flag means "disabled"

    status_msg = "enabled" if new_chat_status else "disabled"
    emit('status', {'msg': f'Host has {status_msg} chat for all non-hosts.', 'type': 'system'}, room=CHAT_ROOM)
    
    emit('update_chat_status', {'enabled': new_chat_status}, room=CHAT_ROOM) # Send the client-friendly "enabled" state
    
    # No need to iterate and set chat_disabled in user_info for each user as it's a global flag now.
    # The client-side 'update_chat_status' listener will handle UI updates.

    for host_sid in hosts:
        emit('update_user_list', {'users': user_info}, room=host_sid)

@socketio.on('request_initial_state')
def request_initial_state():
    sid = request.sid
    video_url_to_send = None
    if current_shared_video_server_path:
        video_url_to_send = f"/videos/{os.path.basename(current_shared_video_server_path)}"
        
    emit('initial_state', {
        'chat_enabled': not chat_disabled_for_all,
        'current_video_url': video_url_to_send,
        'is_host_password_set': bool(HOST_PASSWORD) # Indicate if host password is set for UI
    }, room=sid)

@socketio.on('get_my_user_status')
def get_my_user_status(data, callback): # Added callback argument
    sid = request.sid
    status = user_info.get(sid, {'username': 'Anonymous', 'is_host': False, 'is_muted': False})
    callback(status) # Use the callback to send status back to the client

# --- Video Sharing Backend (Server-Relayed) ---

@app.route('/upload_video', methods=['POST'])
def upload_video():
    # Simple check for host status via SID in query param for HTTP endpoint
    # A more robust solution for production would use Flask-Login or similar for session management.
    requester_sid = request.args.get('sid')
    if requester_sid not in hosts:
        return json.dumps({'success': False, 'error': 'Permission denied: Not a host'}), 403

    if 'video' not in request.files:
        return json.dumps({'success': False, 'error': 'No video file provided'}), 400

    video_file = request.files['video']
    if video_file.filename == '':
        return json.dumps({'success': False, 'error': 'No selected file'}), 400

    if video_file:
        global current_shared_video_server_path
        # Clear existing uploads before saving new one
        # This is a simple approach. For production, consider proper file management
        # to avoid race conditions or accidental deletion of needed files.
        if os.path.exists(UPLOAD_FOLDER):
            # Ensure the directory is empty but exists
            for item in os.listdir(UPLOAD_FOLDER):
                item_path = os.path.join(UPLOAD_FOLDER, item)
                if os.path.isfile(item_path):
                    os.unlink(item_path)
                elif os.path.isdir(item_path):
                    shutil.rmtree(item_path)
        else:
            os.makedirs(UPLOAD_FOLDER)

        # Sanitize filename to prevent directory traversal attacks
        filename = secure_filename(video_file.filename)
        # Add a unique prefix to prevent name collisions
        filename = f"shared_video_{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}_{filename}"
        file_path = os.path.join(UPLOAD_FOLDER, filename)
        video_file.save(file_path)
        current_shared_video_server_path = file_path
        
        video_url = f"/videos/{filename}"
        return json.dumps({'success': True, 'video_url': video_url}), 200
    
    return json.dumps({'success': False, 'error': 'Unknown error during upload'}), 500

# Helper for secure filenames
from werkzeug.utils import secure_filename

@app.route('/videos/<filename>')
def serve_video(filename):
    file_path = os.path.join(UPLOAD_FOLDER, filename)
    # Basic security: ensure the requested filename is within the UPLOAD_FOLDER
    # and doesn't try to access files outside it.
    if not os.path.exists(file_path) or not os.path.commonprefix([file_path, UPLOAD_FOLDER]) == UPLOAD_FOLDER:
        return "Video not found", 404

    range_header = request.headers.get('Range', None)
    if not range_header:
        # If no range header, serve the whole file directly
        return send_from_directory(UPLOAD_FOLDER, filename, mimetype='video/mp4')

    size = os.path.getsize(file_path)
    byte1, byte2 = 0, size - 1

    # Using a more robust regex for range parsing
    match = re.search(r'bytes=(\d+)-(\d*)', range_header)
    if not match:
        return "Invalid Range header", 416 # Requested Range Not Satisfiable

    g = match.groups()

    if g[0]: byte1 = int(g[0])
    if g[1]: byte2 = int(g[1]) if g[1] else size - 1

    length = byte2 - byte1 + 1
    
    resp_data = None
    try:
        with open(file_path, 'rb') as f:
            f.seek(byte1)
            resp_data = f.read(length)
    except IOError:
        return "Internal Server Error", 500

    resp = Response(resp_data, 206, mimetype='video/mp4',
                    headers={'Content-Range': f'bytes {byte1}-{byte2}/{size}',
                             'Accept-Ranges': 'bytes'})
    return resp

@socketio.on('host_starts_video_share')
def host_starts_video_share(data):
    sid = request.sid
    if sid not in hosts:
        emit('status', {'msg': 'Permission denied: Only hosts can share video.', 'type': 'error'}, room=sid)
        return
    
    video_url = data.get('video_url', '')
    if video_url:
        emit('start_video_playback', {'video_url': video_url}, room=CHAT_ROOM)
        emit('status', {'msg': f'Host is sharing a video!', 'type': 'system'}, room=CHAT_ROOM)
        print(f"Host {sid} starting video share: {video_url}")
    else:
        emit('status', {'msg': 'No video URL provided for sharing.', 'type': 'error'}, room=sid)

@socketio.on('host_clears_video')
def host_clears_video():
    sid = request.sid
    if sid not in hosts:
        emit('status', {'msg': 'Permission denied: Only hosts can clear video.', 'type': 'error'}, room=sid)
        return
    
    global current_shared_video_server_path
    current_shared_video_server_path = None
    
    # Safely clear the upload directory contents
    if os.path.exists(UPLOAD_FOLDER):
        for item in os.listdir(UPLOAD_FOLDER):
            item_path = os.path.join(UPLOAD_FOLDER, item)
            try:
                if os.path.isfile(item_path) or os.path.islink(item_path):
                    os.unlink(item_path)
                elif os.path.isdir(item_path):
                    shutil.rmtree(item_path)
            except Exception as e:
                print(f'Failed to delete {item_path}. Reason: {e}')

    emit('clear_video_playback', room=CHAT_ROOM)
    emit('status', {'msg': f'Host has stopped sharing the video.', 'type': 'system'}, room=CHAT_ROOM)

@socketio.on('host_video_control')
def host_video_control(data):
    sid = request.sid
    if sid not in hosts:
        return
    emit('sync_video_playback', data, room=CHAT_ROOM, include_self=False)

if __name__ == '__main__':
    # For production, you should use a production-ready WSGI server like Gunicorn
    # along with an asynchronous worker like eventlet or gevent.
    # Example command for Gunicorn:
    # gunicorn -k eventlet -w 1 main:app --bind 0.0.0.0:5000
    # Or, if you need to run the SocketIO server directly:
    # gunicorn -k geventwebsocket.gunicorn.workers.GeventWebSocketWorker -w 1 main:app --bind 0.0.0.0:5000
    
    # The 'allow_unsafe_werkzeug=True' is for development and should be removed in production.
    # debug=True should also be False in production for security and performance.
    socketio.run(app, debug=False, host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))