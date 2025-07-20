#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# flask_model_rr_server.py
# 
# Copyright 2025  <perry@perrypi2>
# 
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.

from flask import Flask, render_template_string, request, jsonify
import socket
import json
import logging
from typing import Dict, List, Optional
import threading
from datetime import datetime

# Configure logging
logging.basicConfig(level=logging.ERROR, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Configuration
DEFAULT_SERVER = "perrypi3"
DEFAULT_PORT = 9916
CONNECTION_TIMEOUT = 5.0
TRACK_COUNT = 4
SWITCH_COUNT = 2

app = Flask(__name__)

class ServerConnection:
    """Handles communication with the model railroad server."""
    
    def __init__(self, hostname: str = DEFAULT_SERVER, port: int = DEFAULT_PORT):
        self.hostname = hostname
        self.port = port
        self.timeout = CONNECTION_TIMEOUT
        
    def send_command(self, action: str, **kwargs) -> Dict:
        """Send a command to the server and return response."""
        try:
            command_data = {"action": action}
            command_data.update(kwargs)
            
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as client_socket:
                client_socket.settimeout(self.timeout)
                client_socket.connect((self.hostname, self.port))
                
                json_data = json.dumps(command_data)
                client_socket.sendall(json_data.encode('utf-8'))
                
                # Try to receive response
                try:
                    response = client_socket.recv(1024).decode('utf-8')
                    response_data = json.loads(response)
                    success = response_data.get('status') == 'success'
                except (socket.timeout, json.JSONDecodeError):
                    # Server might not send response, assume success if no error
                    success = True
                    
                logger.info(f"Command '{action}' {'succeeded' if success else 'failed'}")
                return {"success": success, "message": "Command executed"}
                
        except Exception as e:
            logger.error(f"Error sending command '{action}': {e}")
            return {"success": False, "message": str(e)}

# Global connection instance
connection = ServerConnection()

# HTML Template
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Model Railroad Controller</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #1e3c72 0%, #2a5298 100%);
            color: white;
            min-height: 100vh;
            padding: 20px;
        }
        
        .container {
            max-width: 1200px;
            margin: 0 auto;
            background: rgba(255, 255, 255, 0.1);
            border-radius: 15px;
            padding: 30px;
            backdrop-filter: blur(10px);
            box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3);
        }
        
        h1 {
            text-align: center;
            margin-bottom: 30px;
            font-size: 2.5em;
            text-shadow: 2px 2px 4px rgba(0, 0, 0, 0.3);
        }
        
        .section {
            margin-bottom: 30px;
            background: rgba(255, 255, 255, 0.05);
            border-radius: 10px;
            padding: 20px;
            border: 1px solid rgba(255, 255, 255, 0.2);
        }
        
        .section-title {
            font-size: 1.4em;
            margin-bottom: 15px;
            color: #ffd700;
            border-bottom: 2px solid #ffd700;
            padding-bottom: 5px;
        }
        
        .control-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 15px;
            margin-bottom: 20px;
        }
        
        .track-control {
            background: rgba(255, 255, 255, 0.08);
            border-radius: 8px;
            padding: 15px;
            border: 1px solid rgba(255, 255, 255, 0.2);
        }
        
        .track-title {
            font-weight: bold;
            margin-bottom: 10px;
            color: #87ceeb;
        }
        
        .button-group {
            display: flex;
            gap: 8px;
            margin-bottom: 10px;
        }
        
        .btn {
            padding: 8px 16px;
            border: none;
            border-radius: 5px;
            cursor: pointer;
            font-size: 14px;
            font-weight: 500;
            transition: all 0.3s ease;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }
        
        .btn:hover {
            transform: translateY(-2px);
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
        }
        
        .btn-primary {
            background: linear-gradient(45deg, #4CAF50, #45a049);
            color: white;
        }
        
        .btn-secondary {
            background: linear-gradient(45deg, #2196F3, #1976D2);
            color: white;
        }
        
        .btn-danger {
            background: linear-gradient(45deg, #f44336, #d32f2f);
            color: white;
        }
        
        .btn-group {
            background: linear-gradient(45deg, #FF9800, #F57C00);
            color: white;
        }
        
        .speed-control {
            margin-top: 10px;
        }
        
        .speed-control label {
            display: block;
            margin-bottom: 5px;
            font-size: 12px;
            color: #ddd;
        }
        
        .speed-slider {
            width: 100%;
            height: 6px;
            border-radius: 3px;
            background: rgba(255, 255, 255, 0.2);
            outline: none;
            -webkit-appearance: none;
        }
        
        .speed-slider::-webkit-slider-thumb {
            -webkit-appearance: none;
            width: 18px;
            height: 18px;
            border-radius: 50%;
            background: #ffd700;
            cursor: pointer;
            box-shadow: 0 2px 6px rgba(0, 0, 0, 0.3);
        }
        
        .speed-slider::-moz-range-thumb {
            width: 18px;
            height: 18px;
            border-radius: 50%;
            background: #ffd700;
            cursor: pointer;
            border: none;
            box-shadow: 0 2px 6px rgba(0, 0, 0, 0.3);
        }
        
        .speed-value {
            text-align: center;
            margin-top: 5px;
            font-weight: bold;
            color: #ffd700;
        }
        
        .group-controls {
            display: flex;
            flex-wrap: wrap;
            gap: 15px;
            align-items: center;
            margin-bottom: 20px;
        }
        
        .group-speed {
            display: flex;
            align-items: center;
            gap: 10px;
            min-width: 200px;
        }
        
        .switch-controls {
            display: flex;
            flex-wrap: wrap;
            gap: 15px;
        }
        
        .switch-group {
            display: flex;
            gap: 8px;
            align-items: center;
        }
        
        .status {
            position: fixed;
            bottom: 20px;
            right: 20px;
            padding: 12px 20px;
            border-radius: 8px;
            font-weight: bold;
            transition: all 0.3s ease;
            z-index: 1000;
        }
        
        .status.success {
            background: linear-gradient(45deg, #4CAF50, #45a049);
            color: white;
        }
        
        .status.error {
            background: linear-gradient(45deg, #f44336, #d32f2f);
            color: white;
        }
        
        .status.info {
            background: linear-gradient(45deg, #2196F3, #1976D2);
            color: white;
        }
        
        .connection-info {
            position: fixed;
            bottom: 20px;
            left: 20px;
            background: rgba(0, 0, 0, 0.7);
            padding: 8px 12px;
            border-radius: 5px;
            font-size: 12px;
            color: #ddd;
        }
        
        @media (max-width: 768px) {
            .container {
                padding: 20px;
            }
            
            h1 {
                font-size: 2em;
            }
            
            .control-grid {
                grid-template-columns: 1fr;
            }
            
            .group-controls {
                flex-direction: column;
                align-items: stretch;
            }
            
            .group-speed {
                min-width: auto;
            }
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>🚂 Model Railroad Controller</h1>
        
        <!-- Group Controls -->
        <div class="section">
            <div class="section-title">Group Controls (All Tracks)</div>
            <div class="group-controls">
                <button class="btn btn-primary" onclick="sendGroupCommand('all_northbound')">All Northbound</button>
                <button class="btn btn-secondary" onclick="sendGroupCommand('all_southbound')">All Southbound</button>
                <button class="btn btn-danger" onclick="sendGroupCommand('all_stop')">All Stop</button>
                <div class="group-speed">
                    <label>Group Speed:</label>
                    <input type="range" id="groupSpeed" class="speed-slider" min="0" max="255" value="0" oninput="updateGroupSpeed(this.value)">
                    <span id="groupSpeedValue" class="speed-value">0</span>
                </div>
            </div>
        </div>
        
        <!-- Individual Track Controls -->
        <div class="section">
            <div class="section-title">Individual Track Controls</div>
            <div class="control-grid" id="trackControls">
                <!-- Track controls will be generated by JavaScript -->
            </div>
        </div>
        
        <!-- Switch Controls -->
        <div class="section">
            <div class="section-title">Switch Controls</div>
            <div class="switch-controls" id="switchControls">
                <!-- Switch controls will be generated by JavaScript -->
            </div>
        </div>
    </div>
    
    <!-- Status Display -->
    <div id="status" class="status info" style="display: none;">Ready</div>
    
    <!-- Connection Info -->
    <div class="connection-info">
        Connected to: {{ server_info }}
    </div>
    
    <script>
        const TRACK_COUNT = {{ track_count }};
        const SWITCH_COUNT = {{ switch_count }};
        
        // Initialize track controls
        function initializeTrackControls() {
            const container = document.getElementById('trackControls');
            
            for (let i = 0; i < TRACK_COUNT; i++) {
                const trackDiv = document.createElement('div');
                trackDiv.className = 'track-control';
                trackDiv.innerHTML = `
                    <div class="track-title">Track ${i}</div>
                    <div class="button-group">
                        <button class="btn btn-primary" onclick="sendTrackCommand(${i}, 'nb')">NB</button>
                        <button class="btn btn-secondary" onclick="sendTrackCommand(${i}, 'sb')">SB</button>
                        <button class="btn btn-danger" onclick="sendTrackCommand(${i}, 'stop')">Stop</button>
                    </div>
                    <div class="speed-control">
                        <label>Speed:</label>
                        <input type="range" id="trackSpeed${i}" class="speed-slider" min="0" max="255" value="0" oninput="updateTrackSpeed(${i}, this.value)">
                        <div class="speed-value" id="trackSpeedValue${i}">0</div>
                    </div>
                `;
                container.appendChild(trackDiv);
            }
        }
        
        // Initialize switch controls
        function initializeSwitchControls() {
            const container = document.getElementById('switchControls');
            
            for (let i = 0; i < SWITCH_COUNT; i++) {
                const switchDiv = document.createElement('div');
                switchDiv.className = 'switch-group';
                switchDiv.innerHTML = `
                    <span>Switch ${i}:</span>
                    <button class="btn btn-primary" onclick="sendSwitchCommand(${i}, 'direct')">Direct</button>
                    <button class="btn btn-secondary" onclick="sendSwitchCommand(${i}, 'diverge')">Diverge</button>
                `;
                container.appendChild(switchDiv);
            }
        }
        
        // Show status message
        function showStatus(message, type = 'info') {
            const status = document.getElementById('status');
            status.textContent = message;
            status.className = `status ${type}`;
            status.style.display = 'block';
            
            setTimeout(() => {
                status.style.display = 'none';
            }, 3000);
        }
        
        // Send command to server
        async function sendCommand(endpoint, data = {}) {
            try {
                showStatus('Sending command...', 'info');
                
                const response = await fetch(endpoint, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify(data)
                });
                
                const result = await response.json();
                
                if (result.success) {
                    showStatus('Command successful', 'success');
                } else {
                    showStatus(`Command failed: ${result.message}`, 'error');
                }
                
                return result;
            } catch (error) {
                showStatus(`Error: ${error.message}`, 'error');
                return { success: false, message: error.message };
            }
        }
        
        // Group command functions
        async function sendGroupCommand(action) {
            await sendCommand('/group', { action });
        }
        
        // Track command functions
        async function sendTrackCommand(trackId, action) {
            await sendCommand('/track', { track_id: trackId, action });
        }
        
        async function updateTrackSpeed(trackId, speed) {
            document.getElementById(`trackSpeedValue${trackId}`).textContent = speed;
            await sendCommand('/track', { track_id: trackId, action: 'speed', speed: parseInt(speed) });
        }
        
        // Switch command functions
        async function sendSwitchCommand(switchId, action) {
            await sendCommand('/switch', { switch_id: switchId, action });
        }
        
        // Group speed functions
        async function updateGroupSpeed(speed) {
            document.getElementById('groupSpeedValue').textContent = speed;
            
            // Update all individual track sliders
            for (let i = 0; i < TRACK_COUNT; i++) {
                const slider = document.getElementById(`trackSpeed${i}`);
                const value = document.getElementById(`trackSpeedValue${i}`);
                slider.value = speed;
                value.textContent = speed;
            }
            
            await sendCommand('/group', { action: 'speed', speed: parseInt(speed) });
        }
        
        // Initialize the interface when page loads
        document.addEventListener('DOMContentLoaded', function() {
            initializeTrackControls();
            initializeSwitchControls();
            showStatus('Interface loaded', 'success');
        });
    </script>
</body>
</html>
"""

@app.route('/')
def index():
    """Serve the main control interface."""
    server_info = f"{connection.hostname}:{connection.port}"
    return render_template_string(HTML_TEMPLATE, 
                                server_info=server_info,
                                track_count=TRACK_COUNT,
                                switch_count=SWITCH_COUNT)

@app.route('/group', methods=['POST'])
def handle_group_command():
    """Handle group control commands."""
    data = request.get_json()
    action = data.get('action')
    
    if action == 'all_northbound':
        results = []
        for i in range(TRACK_COUNT):
            result = connection.send_command(f"track{i}_nb")
            results.append(result)
        success = all(r['success'] for r in results)
        
    elif action == 'all_southbound':
        results = []
        for i in range(TRACK_COUNT):
            result = connection.send_command(f"track{i}_sb")
            results.append(result)
        success = all(r['success'] for r in results)
        
    elif action == 'all_stop':
        results = []
        for i in range(TRACK_COUNT):
            result = connection.send_command(f"track{i}_stop")
            results.append(result)
        success = all(r['success'] for r in results)
        
    elif action == 'speed':
        speed = data.get('speed', 0)
        results = []
        for i in range(TRACK_COUNT):
            result = connection.send_command(f"track{i}_speed", speed=speed)
            results.append(result)
        success = all(r['success'] for r in results)
        
    else:
        return jsonify({"success": False, "message": "Invalid action"})
    
    return jsonify({"success": success, "message": "Group command executed"})

@app.route('/track', methods=['POST'])
def handle_track_command():
    """Handle individual track commands."""
    data = request.get_json()
    track_id = data.get('track_id')
    action = data.get('action')
    
    if track_id is None or track_id < 0 or track_id >= TRACK_COUNT:
        return jsonify({"success": False, "message": "Invalid track ID"})
    
    if action == 'nb':
        result = connection.send_command(f"track{track_id}_nb")
    elif action == 'sb':
        result = connection.send_command(f"track{track_id}_sb")
    elif action == 'stop':
        result = connection.send_command(f"track{track_id}_stop")
    elif action == 'speed':
        speed = data.get('speed', 0)
        if not (0 <= speed <= 255):
            return jsonify({"success": False, "message": "Speed must be 0-255"})
        result = connection.send_command(f"track{track_id}_speed", speed=speed)
    else:
        return jsonify({"success": False, "message": "Invalid action"})
    
    return jsonify(result)

@app.route('/switch', methods=['POST'])
def handle_switch_command():
    """Handle switch commands."""
    data = request.get_json()
    switch_id = data.get('switch_id')
    action = data.get('action')
    
    if switch_id is None or switch_id < 0 or switch_id >= SWITCH_COUNT:
        return jsonify({"success": False, "message": "Invalid switch ID"})
    
    if action == 'direct':
        result = connection.send_command(f"switch{switch_id}_direct")
    elif action == 'diverge':
        result = connection.send_command(f"switch{switch_id}_diverge")
    else:
        return jsonify({"success": False, "message": "Invalid action"})
    
    return jsonify(result)

@app.route('/status', methods=['GET'])
def get_status():
    """Get system status."""
    return jsonify({
        "server": f"{connection.hostname}:{connection.port}",
        "track_count": TRACK_COUNT,
        "switch_count": SWITCH_COUNT,
        "timestamp": datetime.now().isoformat()
    })

def main():
    """Main function to run the Flask app."""
    try:
        logger.info("Starting Flask Model Railroad Server")
        logger.info(f"Connecting to railroad server: {connection.hostname}:{connection.port}")
        
        # Run Flask app
        app.run(
            host='0.0.0.0',  # Listen on all interfaces
            port=5000,       # Web server port
            debug=False,     # Set to True for development
            threaded=True    # Handle multiple requests
        )
        
    except KeyboardInterrupt:
        logger.info("Server interrupted")
    except Exception as e:
        logger.error(f"Server error: {e}")
        return 1
    finally:
        logger.info("Server shutting down")
    
    return 0

if __name__ == '__main__':
    import sys
    sys.exit(main())