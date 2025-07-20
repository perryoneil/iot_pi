#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
#  model_rr_client.py
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

# 7/20/2025: Perry O'Neil corrected Claude error (convert string to Int).
# 7/20/2025: Claude refactored Perry O'Neil's code.

import tkinter as tk
from tkinter import messagebox, ttk
import socket
import json
import logging
from typing import Dict, List, Optional, Tuple
import sys
import threading

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Configuration
DEFAULT_SERVER = "perrypi3"
DEFAULT_PORT = 9916
CONNECTION_TIMEOUT = 5.0

# Track and switch configurations
TRACK_COUNT = 4
SWITCH_COUNT = 2


class ServerConnection:
    """Handles communication with the model railroad server."""
    
    def __init__(self, hostname: str = DEFAULT_SERVER, port: int = DEFAULT_PORT):
        self.hostname = hostname
        self.port = port
        self.timeout = CONNECTION_TIMEOUT
        
    def send_command(self, action: str, **kwargs) -> bool:
        """Send a command to the server and return success status."""
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
                    logger.info(f"Command '{action}' {'succeeded' if success else 'failed'}")
                    return success
                except (socket.timeout, json.JSONDecodeError):
                    # Server might not send response, assume success if no error
                    logger.info(f"Command '{action}' sent (no response received)")
                    return True
                    
        except Exception as e:
            logger.error(f"Error sending command '{action}': {e}")
            return False


class TrackController:
    """Controls a single track with direction and speed."""
    
    def __init__(self, track_id: int, connection: ServerConnection):
        self.track_id = track_id
        self.connection = connection
        self.current_speed = 0
        
    def northbound(self) -> bool:
        """Set track direction to northbound."""
        return self.connection.send_command(f"track{self.track_id}_nb")
        
    def southbound(self) -> bool:
        """Set track direction to southbound."""
        return self.connection.send_command(f"track{self.track_id}_sb")
        
    def stop(self) -> bool:
        """Stop the track."""
        return self.connection.send_command(f"track{self.track_id}_stop")
        
    def set_speed(self, speed: int) -> bool:
        """Set track speed (0-255)."""
        if 0 <= speed <= 255:
            self.current_speed = speed
            return self.connection.send_command(f"track{self.track_id}_speed", speed=speed)
        return False


class SwitchController:
    """Controls a single switch with direct/diverge positions."""
    
    def __init__(self, switch_id: int, connection: ServerConnection):
        self.switch_id = switch_id
        self.connection = connection
        
    def direct(self) -> bool:
        """Set switch to direct position."""
        return self.connection.send_command(f"switch{self.switch_id}_direct")
        
    def diverge(self) -> bool:
        """Set switch to diverge position."""
        return self.connection.send_command(f"switch{self.switch_id}_diverge")


class GroupController:
    """Controls multiple tracks as a group."""
    
    def __init__(self, tracks: List[TrackController]):
        self.tracks = tracks
        
    def all_northbound(self) -> bool:
        """Set all tracks in group to northbound."""
        return all(track.northbound() for track in self.tracks)
        
    def all_southbound(self) -> bool:
        """Set all tracks in group to southbound."""
        return all(track.southbound() for track in self.tracks)
        
    def all_stop(self) -> bool:
        """Stop all tracks in group."""
        return all(track.stop() for track in self.tracks)
        
    def set_all_speed(self, speed: int) -> bool:
        """Set speed for all tracks in group."""
        return all(track.set_speed(speed) for track in self.tracks)


class ModelRailroadGUI:
    """Main GUI application for the model railroad client."""
    
    def __init__(self, master: tk.Tk):
        self.master = master
        self.connection = ServerConnection()
        
        # Initialize controllers
        self.tracks = [TrackController(i, self.connection) for i in range(TRACK_COUNT)]
        self.switches = [SwitchController(i, self.connection) for i in range(SWITCH_COUNT)]
        self.group_controller = GroupController(self.tracks)
        
        # GUI setup
        self.setup_window()
        self.create_widgets()
        
    def setup_window(self):
        """Configure the main window."""
        self.master.title("Model Railroad Controller")
        self.master.geometry('850x400')
        self.master.resizable(True, True)
        
        # Configure grid weights for responsive layout
        for i in range(6):  # Number of rows
            self.master.grid_rowconfigure(i, weight=1)
        for i in range(5):  # Number of columns
            self.master.grid_columnconfigure(i, weight=1)
            
    def create_widgets(self):
        """Create all GUI widgets."""
        # Header
        header_frame = ttk.Frame(self.master)
        header_frame.grid(row=0, column=0, columnspan=5, sticky='ew', padx=5, pady=5)
        
        ttk.Label(header_frame, text="Model Railroad Controller", 
                 font=('Arial', 16, 'bold')).pack()
        
        # Group controls
        self.create_group_controls()
        
        # Individual track controls
        self.create_track_controls()
        
        # Switch controls
        self.create_switch_controls()
        
        # Status bar
        self.create_status_bar()
        
    def create_group_controls(self):
        """Create group control widgets."""
        group_frame = ttk.LabelFrame(self.master, text="Group Controls (All Tracks)")
        group_frame.grid(row=1, column=0, columnspan=5, sticky='ew', padx=5, pady=2)
        
        # Configure group frame columns
        for i in range(4):
            group_frame.grid_columnconfigure(i, weight=1)
            
        ttk.Button(group_frame, text="All Northbound", 
                  command=self.safe_command(self.group_controller.all_northbound)
                  ).grid(row=0, column=0, padx=2, pady=2, sticky='ew')
                  
        ttk.Button(group_frame, text="All Southbound",
                  command=self.safe_command(self.group_controller.all_southbound)
                  ).grid(row=0, column=1, padx=2, pady=2, sticky='ew')
                  
        ttk.Button(group_frame, text="All Stop",
                  command=self.safe_command(self.group_controller.all_stop)
                  ).grid(row=0, column=2, padx=2, pady=2, sticky='ew')
        
        # Group speed control
        speed_frame = ttk.Frame(group_frame)
        speed_frame.grid(row=0, column=3, padx=2, pady=2, sticky='ew')
        
        ttk.Label(speed_frame, text="Group Speed:").pack(side='left')
        self.group_speed_var = tk.IntVar(value=0)
        group_speed_scale = ttk.Scale(speed_frame, from_=0, to=255, 
                                     orient='horizontal', variable=self.group_speed_var,
                                     command=self.on_group_speed_change)
        group_speed_scale.pack(side='left', fill='x', expand=True, padx=5)
        
        self.group_speed_label = ttk.Label(speed_frame, text="0")
        self.group_speed_label.pack(side='left')
        
    def create_track_controls(self):
        """Create individual track control widgets."""
        tracks_frame = ttk.LabelFrame(self.master, text="Individual Track Controls")
        tracks_frame.grid(row=2, column=0, columnspan=5, rowspan=3, sticky='nsew', padx=5, pady=2)
        
        # Configure tracks frame
        for i in range(TRACK_COUNT):
            tracks_frame.grid_rowconfigure(i, weight=1)
        for i in range(5):
            tracks_frame.grid_columnconfigure(i, weight=1)
            
        # Create controls for each track
        self.track_speed_vars = []
        self.track_speed_labels = []
        
        for i in range(TRACK_COUNT):
            # Track label
            ttk.Label(tracks_frame, text=f"Track {i}:").grid(
                row=i, column=0, padx=2, pady=2, sticky='w')
            
            # Direction buttons
            ttk.Button(tracks_frame, text="NB",
                      command=self.safe_command(self.tracks[i].northbound)
                      ).grid(row=i, column=1, padx=2, pady=2, sticky='ew')
                      
            ttk.Button(tracks_frame, text="SB",
                      command=self.safe_command(self.tracks[i].southbound)
                      ).grid(row=i, column=2, padx=2, pady=2, sticky='ew')
                      
            ttk.Button(tracks_frame, text="Stop",
                      command=self.safe_command(self.tracks[i].stop)
                      ).grid(row=i, column=3, padx=2, pady=2, sticky='ew')
            
            # Speed control
            speed_frame = ttk.Frame(tracks_frame)
            speed_frame.grid(row=i, column=4, padx=2, pady=2, sticky='ew')
            speed_frame.grid_columnconfigure(0, weight=1)
            
            speed_var = tk.IntVar(value=0)
            self.track_speed_vars.append(speed_var)
            
            speed_scale = ttk.Scale(speed_frame, from_=0, to=255, orient='horizontal',
                                   variable=speed_var,
                                   command=lambda val, track_id=i: self.on_track_speed_change(track_id, val))
            speed_scale.grid(row=0, column=0, sticky='ew')
            
            speed_label = ttk.Label(speed_frame, text="0")
            speed_label.grid(row=0, column=1, padx=5)
            self.track_speed_labels.append(speed_label)
            
    def create_switch_controls(self):
        """Create switch control widgets."""
        switch_frame = ttk.LabelFrame(self.master, text="Switch Controls")
        switch_frame.grid(row=5, column=0, columnspan=5, sticky='ew', padx=5, pady=2)
        
        # Configure switch frame columns
        for i in range(SWITCH_COUNT * 2):
            switch_frame.grid_columnconfigure(i, weight=1)
            
        for i in range(SWITCH_COUNT):
            col_offset = i * 2
            ttk.Button(switch_frame, text=f"Switch {i} Direct",
                      command=self.safe_command(self.switches[i].direct)
                      ).grid(row=0, column=col_offset, padx=2, pady=2, sticky='ew')
                      
            ttk.Button(switch_frame, text=f"Switch {i} Diverge",
                      command=self.safe_command(self.switches[i].diverge)
                      ).grid(row=0, column=col_offset + 1, padx=2, pady=2, sticky='ew')
                      
    def create_status_bar(self):
        """Create status bar."""
        status_frame = ttk.Frame(self.master)
        status_frame.grid(row=6, column=0, columnspan=5, sticky='ew', padx=5, pady=2)
        
        self.status_var = tk.StringVar(value="Ready")
        status_label = ttk.Label(status_frame, textvariable=self.status_var, relief='sunken')
        status_label.pack(fill='x')
        
        # Connection info
        connection_info = f"Connected to: {self.connection.hostname}:{self.connection.port}"
        ttk.Label(status_frame, text=connection_info, font=('Arial', 8)).pack(anchor='e')
        
    def safe_command(self, command_func):
        """Wrap commands with error handling and status updates."""
        def wrapper():
            try:
                self.status_var.set("Sending command...")
                self.master.update_idletasks()
                
                # Run command in thread to prevent GUI freezing
                def run_command():
                    try:
                        success = command_func()
                        status = "Command successful" if success else "Command failed"
                        self.master.after(0, lambda: self.status_var.set(status))
                    except Exception as e:
                        error_msg = f"Error: {str(e)}"
                        self.master.after(0, lambda: self.status_var.set(error_msg))
                        logger.error(f"Command error: {e}")
                        
                thread = threading.Thread(target=run_command, daemon=True)
                thread.start()
                
            except Exception as e:
                self.status_var.set(f"Error: {str(e)}")
                logger.error(f"Command wrapper error: {e}")
                
        return wrapper
        
    def on_group_speed_change(self, value):
        """Handle group speed slider change."""
        speed = int(float(value))
        self.group_speed_label.config(text=str(speed))
        
        # Update all individual track sliders
        for speed_var in self.track_speed_vars:
            speed_var.set(speed)
            
        # Send command
        self.safe_command(lambda: self.group_controller.set_all_speed(speed))()
        
    def on_track_speed_change(self, track_id: int, value):
        """Handle individual track speed slider change."""
        speed = int(float(value))
        self.track_speed_labels[track_id].config(text=str(speed))
        self.safe_command(lambda: self.tracks[track_id].set_speed(speed))()


class ModelRailroadApp:
    """Main application class."""
    
    def __init__(self):
        self.root = tk.Tk()
        self.gui = ModelRailroadGUI(self.root)
        
    def run(self):
        """Start the application."""
        try:
            logger.info("Starting Model Railroad Client")
            self.root.mainloop()
        except KeyboardInterrupt:
            logger.info("Application interrupted")
        except Exception as e:
            logger.error(f"Application error: {e}")
            messagebox.showerror("Error", f"Application error: {e}")
        finally:
            logger.info("Application shutting down")


def main():
    """Main function."""
    try:
        app = ModelRailroadApp()
        app.run()
        return 0
    except Exception as e:
        logger.error(f"Main function error: {e}")
        return 1


if __name__ == '__main__':
    sys.exit(main())