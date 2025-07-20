#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
#  model_rr_server.py
#  
#  Copyright 2025  <perry@perrypi2>
#  
#  This program is free software; you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation; either version 2 of the License, or
#  (at your option) any later version.
#  
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#  
#  You should have received a copy of the GNU General Public License
#  along with this program; if not, write to the Free Software
#  Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston,
#  MA 02110-1301, USA.

import socket
import pigpio
import logging
import time
import json
import sys
from typing import Dict, List, Tuple, Optional

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Pin configuration
STATUS_INDICATOR = 25
SERVER_PORT = 9916

# Track and switch configurations
TRACK_CONFIG = {
    0: {'nb': 4, 'sb': 5, 'speed': 18},
    1: {'nb': 6, 'sb': 12, 'speed': 19},
    2: {'nb': 13, 'sb': 16, 'speed': 17},
    3: {'nb': 22, 'sb': 23, 'speed': 24}
}

SWITCH_CONFIG = {
    0: {'direct': 13, 'diverge': 16, 'trigger': 17},
    1: {'direct': 22, 'diverge': 23, 'trigger': 24}
}

PWM_FREQUENCY = 20000
DEFAULT_SPEED = 50
SWITCH_TRIGGER_DURATION = 0.5


class Track:
    """Represents a model railroad track with direction and speed control."""
    
    def __init__(self, track_id: int, nb_pin: int, sb_pin: int, speed_pin: int, rpi: pigpio.pi):
        self.track_id = track_id
        self.nb_pin = nb_pin
        self.sb_pin = sb_pin
        self.speed_pin = speed_pin
        self.rpi = rpi
        self.current_speed = 0
        
    def northbound(self) -> None:
        """Set track direction to northbound."""
        current_state = self.rpi.read(self.nb_pin)
        self.rpi.write(self.nb_pin, 1 if current_state == 0 else 0)
        self.rpi.write(self.sb_pin, 0)
        logger.info(f"Track {self.track_id}: Northbound")
        
    def southbound(self) -> None:
        """Set track direction to southbound."""
        current_state = self.rpi.read(self.sb_pin)
        self.rpi.write(self.sb_pin, 1 if current_state == 0 else 0)
        self.rpi.write(self.nb_pin, 0)
        logger.info(f"Track {self.track_id}: Southbound")
        
    def stop(self) -> None:
        """Stop the track by setting both direction pins to 0."""
        self.rpi.write(self.nb_pin, 0)
        self.rpi.write(self.sb_pin, 0)
        logger.info(f"Track {self.track_id}: Stopped")
        
    def set_speed(self, speed: int) -> None:
        """Set the PWM speed for the track."""
        if 0 <= speed <= 255:
            self.current_speed = speed
            self.rpi.set_PWM_dutycycle(self.speed_pin, speed)
            logger.info(f"Track {self.track_id}: Speed set to {speed}")
        else:
            logger.warning(f"Track {self.track_id}: Invalid speed {speed}. Must be 0-255")


class Switch:
    """Represents a model railroad switch with direct/diverge control."""
    
    def __init__(self, switch_id: int, direct_pin: int, diverge_pin: int, trigger_pin: int, rpi: pigpio.pi):
        self.switch_id = switch_id
        self.direct_pin = direct_pin
        self.diverge_pin = diverge_pin
        self.trigger_pin = trigger_pin
        self.rpi = rpi
        
    def direct(self) -> None:
        """Set switch to direct position."""
        self.rpi.write(self.direct_pin, 1)
        self.rpi.write(self.diverge_pin, 0)
        self.rpi.write(self.trigger_pin, 1)
        time.sleep(SWITCH_TRIGGER_DURATION)
        self.rpi.write(self.trigger_pin, 0)
        logger.info(f"Switch {self.switch_id}: Direct")
        
    def diverge(self) -> None:
        """Set switch to diverge position."""
        self.rpi.write(self.direct_pin, 0)
        self.rpi.write(self.diverge_pin, 1)
        self.rpi.write(self.trigger_pin, 1)
        time.sleep(SWITCH_TRIGGER_DURATION)
        self.rpi.write(self.trigger_pin, 0)
        logger.info(f"Switch {self.switch_id}: Diverge")


class ModelRailroadController:
    """Main controller for the model railroad system."""
    
    def __init__(self):
        self.rpi = None
        self.tracks: Dict[int, Track] = {}
        self.switches: Dict[int, Switch] = {}
        self.server_socket = None
        
    def initialize_gpio(self) -> bool:
        """Initialize GPIO pins and create track/switch objects."""
        try:
            self.rpi = pigpio.pi()
            if not self.rpi.connected:
                logger.error("Failed to connect to pigpio daemon")
                return False
                
            # Initialize tracks
            for track_id, config in TRACK_CONFIG.items():
                # Set up control pins
                for pin_type in ['nb', 'sb']:
                    pin = config[pin_type]
                    self.rpi.set_mode(pin, pigpio.OUTPUT)
                    self.rpi.set_pull_up_down(pin, pigpio.PUD_UP)
                    
                # Set up speed pin
                speed_pin = config['speed']
                self.rpi.set_mode(speed_pin, pigpio.OUTPUT)
                self.rpi.set_pull_up_down(speed_pin, pigpio.PUD_UP)
                self.rpi.set_PWM_dutycycle(speed_pin, 0)
                self.rpi.set_PWM_frequency(speed_pin, PWM_FREQUENCY)
                
                # Create track object
                self.tracks[track_id] = Track(
                    track_id, config['nb'], config['sb'], config['speed'], self.rpi
                )
                
            # Initialize switches
            for switch_id, config in SWITCH_CONFIG.items():
                for pin in config.values():
                    self.rpi.set_mode(pin, pigpio.OUTPUT)
                    self.rpi.set_pull_up_down(pin, pigpio.PUD_UP)
                    
                self.switches[switch_id] = Switch(
                    switch_id, config['direct'], config['diverge'], config['trigger'], self.rpi
                )
                
            # Initialize status indicator
            self.rpi.set_mode(STATUS_INDICATOR, pigpio.OUTPUT)
            self.rpi.set_pull_up_down(STATUS_INDICATOR, pigpio.PUD_UP)
            
            logger.info("GPIO initialization complete")
            return True
            
        except Exception as e:
            logger.error(f"GPIO initialization failed: {e}")
            return False
            
    def process_command(self, command_data: Dict) -> bool:
        """Process incoming command from client."""
        try:
            action = command_data.get('action')
            if not action:
                logger.warning("No action specified in command")
                return False
                
            # Parse action
            parts = action.split('_')
            if len(parts) < 2:
                logger.warning(f"Invalid action format: {action}")
                return False
                
            device_type = parts[0]  # 'track' or 'switch'
            device_id = int(parts[0][-1])  # Extract number from track0, track1, etc.
            command = '_'.join(parts[1:])  # The rest is the command
            
            if device_type.startswith('track'):
                return self._handle_track_command(device_id, command, command_data)
            elif device_type.startswith('switch'):
                return self._handle_switch_command(device_id, command, command_data)
            else:
                logger.warning(f"Unknown device type: {device_type}")
                return False
                
        except Exception as e:
            logger.error(f"Error processing command: {e}")
            return False
            
    def _handle_track_command(self, track_id: int, command: str, command_data: Dict) -> bool:
        """Handle track-specific commands."""
        if track_id not in self.tracks:
            logger.warning(f"Track {track_id} not found")
            return False
            
        track = self.tracks[track_id]
        
        if command == 'nb':
            track.northbound()
        elif command == 'sb':
            track.southbound()
        elif command == 'stop':
            track.stop()
        elif command == 'speed':
            speed = int(command_data.get('speed', DEFAULT_SPEED))
            track.set_speed(speed)
        else:
            logger.warning(f"Unknown track command: {command}")
            return False
            
        return True
        
    def _handle_switch_command(self, switch_id: int, command: str, command_data: Dict) -> bool:
        """Handle switch-specific commands."""
        if switch_id not in self.switches:
            logger.warning(f"Switch {switch_id} not found")
            return False
            
        switch = self.switches[switch_id]
        
        if command == 'direct':
            switch.direct()
        elif command == 'diverge':
            switch.diverge()
        else:
            logger.warning(f"Unknown switch command: {command}")
            return False
            
        return True
        
    def start_server(self) -> None:
        """Start the TCP server to listen for commands."""
        try:
            self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.server_socket.bind(('', SERVER_PORT))
            self.server_socket.listen(1)
            
            logger.info(f"Server listening on port {SERVER_PORT}")
            
            while True:
                try:
                    client_socket, addr = self.server_socket.accept()
                    logger.info(f"Connection from {addr}")
                    
                    # Receive data with timeout
                    client_socket.settimeout(10.0)
                    data = client_socket.recv(1024).decode('utf-8')
                    
                    if data:
                        command_data = json.loads(data)
                        logger.info(f"Received command: {command_data}")
                        
                        success = self.process_command(command_data)
                        
                        # Send response
                        response = {'status': 'success' if success else 'error'}
                        client_socket.send(json.dumps(response).encode('utf-8'))
                    
                except socket.timeout:
                    logger.warning("Client connection timed out")
                except json.JSONDecodeError as e:
                    logger.error(f"Invalid JSON received: {e}")
                except Exception as e:
                    logger.error(f"Error handling client connection: {e}")
                finally:
                    try:
                        client_socket.close()
                    except:
                        pass
                        
        except KeyboardInterrupt:
            logger.info("Server shutting down...")
        except Exception as e:
            logger.error(f"Server error: {e}")
        finally:
            self.cleanup()
            
    def cleanup(self) -> None:
        """Clean up resources."""
        try:
            if self.server_socket:
                self.server_socket.close()
                
            if self.rpi:
                # Stop all tracks
                for track in self.tracks.values():
                    track.stop()
                    track.set_speed(0)
                    
                # Turn off status indicator
                self.rpi.write(STATUS_INDICATOR, 0)
                
                self.rpi.stop()
                
            logger.info("Cleanup complete")
            
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")


def main():
    """Main function to start the model railroad controller."""
    controller = ModelRailroadController()
    
    if not controller.initialize_gpio():
        logger.error("Failed to initialize GPIO. Exiting.")
        return 1
        
    try:
        controller.start_server()
    except KeyboardInterrupt:
        logger.info("Received interrupt signal")
    finally:
        controller.cleanup()
        
    return 0


if __name__ == '__main__':
    sys.exit(main())