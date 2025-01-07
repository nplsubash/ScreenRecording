import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import cv2
import numpy as np
import pyautogui
import tempfile
import time
from pathlib import Path
from datetime import datetime
import sounddevice as sd
import soundfile as sf
import threading
import queue
import os
import subprocess
from PIL import Image, ImageTk

class ScreenRecorderGUI:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Screen & Audio Recorder")
        self.root.geometry("500x750")
        self.root.resizable(False, False)
        
        # Recording state
        self.is_recording = False
        self.frame_queue = queue.Queue()
        self.audio_queue = queue.Queue()
        self.preview_active = False
        
        # Default settings
        self.output_dir = self._get_default_output_dir()
        self.fps = 30
        self.quality = 95
        self.audio_enabled = True
        self.recording_mode = "screen_and_audio"  # New recording mode setting
        
        self._setup_audio()
        self._create_gui()
        self._setup_preview()
    
    def _get_default_output_dir(self):
        """Get or create default output directory"""
        default_dirs = [
            str(Path.home() / "Videos"),
            str(Path.home() / "Documents" / "Recordings"),
            str(Path.home() / "Recordings"),
            str(Path.home())
        ]
        
        # Try to find or create a suitable directory
        for dir_path in default_dirs:
            try:
                path = Path(dir_path)
                if not path.exists():
                    path.mkdir(parents=True)
                if os.access(dir_path, os.W_OK):
                    return str(path)
            except Exception:
                continue
                
        # If no suitable directory found, use temp directory
        return tempfile.gettempdir()
    
    def _setup_audio(self):
        """Configure audio settings"""
        try:
            device_info = sd.query_devices(kind='input')
            if device_info is not None:
                self.channels = min(device_info['max_input_channels'], 2)
                self.sample_rate = int(device_info['default_samplerate'])
                self.available_devices = sd.query_devices()
                self.audio_enabled = True
            else:
                self.audio_enabled = False
        except Exception:
            self.audio_enabled = False
    
    def _create_gui(self):
        """Create the GUI elements"""
        style = ttk.Style()
        style.configure('Custom.TButton', padding=10)
        
        # Main container
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Preview frame
        self.preview_frame = ttk.LabelFrame(main_frame, text="Preview", padding="5")
        self.preview_frame.grid(row=0, column=0, columnspan=2, pady=5, sticky="nsew")
        self.preview_label = ttk.Label(self.preview_frame)
        self.preview_label.grid(row=0, column=0)
        
        # Settings frame
        settings_frame = ttk.LabelFrame(main_frame, text="Settings", padding="10")
        settings_frame.grid(row=1, column=0, columnspan=2, pady=10, sticky="nsew")
        
        # Recording mode selection
        ttk.Label(settings_frame, text="Recording Mode:").grid(row=0, column=0, sticky=tk.W)
        self.mode_var = tk.StringVar(value="screen_and_audio")
        mode_combo = ttk.Combobox(settings_frame, textvariable=self.mode_var, 
                                 values=["Screen & Audio", "Audio Only"], 
                                 width=27, state="readonly")
        mode_combo.grid(row=0, column=1, columnspan=2, sticky=tk.W)
        mode_combo.bind('<<ComboboxSelected>>', self._on_mode_change)
        
        # Output directory
        ttk.Label(settings_frame, text="Output Directory:").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.output_path_var = tk.StringVar(value=self.output_dir)
        ttk.Entry(settings_frame, textvariable=self.output_path_var, width=30).grid(row=1, column=1, padx=5)
        ttk.Button(settings_frame, text="Browse", command=self._browse_output).grid(row=1, column=2)
        
        # FPS setting (only for screen recording)
        self.fps_label = ttk.Label(settings_frame, text="FPS:")
        self.fps_label.grid(row=2, column=0, sticky=tk.W, pady=5)
        self.fps_var = tk.StringVar(value=str(self.fps))
        self.fps_spinbox = ttk.Spinbox(settings_frame, from_=1, to=60, textvariable=self.fps_var, width=10)
        self.fps_spinbox.grid(row=2, column=1, sticky=tk.W, pady=5)
        
        # Quality setting
        self.quality_label = ttk.Label(settings_frame, text="Quality:")
        self.quality_label.grid(row=3, column=0, sticky=tk.W)
        self.quality_var = tk.StringVar(value=str(self.quality))
        self.quality_spinbox = ttk.Spinbox(settings_frame, from_=1, to=100, textvariable=self.quality_var, width=10)
        self.quality_spinbox.grid(row=3, column=1, sticky=tk.W)
        
        # Audio device selection
        if self.audio_enabled:
            ttk.Label(settings_frame, text="Audio Device:").grid(row=4, column=0, sticky=tk.W, pady=5)
            self.audio_device_var = tk.StringVar()
            audio_devices = [device['name'] for device in self.available_devices if device['max_input_channels'] > 0]
            audio_device_combo = ttk.Combobox(settings_frame, textvariable=self.audio_device_var, values=audio_devices, width=27)
            audio_device_combo.grid(row=4, column=1, columnspan=2, sticky=tk.W, pady=5)
            if audio_devices:
                audio_device_combo.set(audio_devices[0])
        
        # Control buttons frame
        control_frame = ttk.Frame(main_frame, padding="5")
        control_frame.grid(row=2, column=0, columnspan=2, pady=10)
        
        # Record button
        self.record_button = ttk.Button(control_frame, text="Start Recording", 
                                      command=self._toggle_recording, style='Custom.TButton')
        self.record_button.grid(row=0, column=0, padx=5)
        
        # Status label
        self.status_var = tk.StringVar(value="Ready to record")
        self.status_label = ttk.Label(main_frame, textvariable=self.status_var)
        self.status_label.grid(row=3, column=0, columnspan=2, pady=10)
    
    def _on_mode_change(self, event=None):
        """Handle recording mode changes"""
        mode = self.mode_var.get()
        is_screen_recording = mode == "Screen & Audio"
        
        # Show/hide screen recording specific controls
        if is_screen_recording:
            self.fps_label.grid()
            self.fps_spinbox.grid()
            self.quality_label.grid()
            self.quality_spinbox.grid()
            self.preview_frame.grid()
        else:
            self.fps_label.grid_remove()
            self.fps_spinbox.grid_remove()
            self.quality_label.grid_remove()
            self.quality_spinbox.grid_remove()
            self.preview_frame.grid_remove()
    
    def _setup_preview(self):
        """Setup the preview window"""
        self.preview_active = True
        self.preview_thread = threading.Thread(target=self._update_preview)
        self.preview_thread.daemon = True
        self.preview_thread.start()
    
    def _update_preview(self):
        """Update the preview image"""
        while self.preview_active:
            if self.mode_var.get() == "Screen & Audio":
                try:
                    screenshot = pyautogui.screenshot()
                    preview_width = 380
                    aspect_ratio = screenshot.height / screenshot.width
                    preview_height = int(preview_width * aspect_ratio)
                    screenshot = screenshot.resize((preview_width, preview_height))
                    
                    photo = ImageTk.PhotoImage(screenshot)
                    self.preview_label.configure(image=photo)
                    self.preview_label.image = photo
                except Exception:
                    pass
            time.sleep(1/10)
    
    def _browse_output(self):
        """Open directory browser"""
        directory = filedialog.askdirectory(initialdir=self.output_dir)
        if directory:
            if os.access(directory, os.W_OK):
                self.output_dir = directory
                self.output_path_var.set(directory)
            else:
                messagebox.showerror("Error", "Selected directory is not writable. Please choose another location.")
    
    def _toggle_recording(self):
        """Toggle recording state"""
        if not self.is_recording:
            self.start_recording()
        else:
            self.stop_recording()
    
    def start_recording(self):
        """Start recording"""
        try:
            if not self._validate_settings():
                return

            self.is_recording = True
            self.record_button.configure(text="Stop Recording")
            
            # Clear any existing queued data
            while not self.audio_queue.empty():
                self.audio_queue.get()
            
            # Update settings from GUI
            self.output_dir = self.output_path_var.get()
            mode = self.mode_var.get()
            
            if mode == "Screen & Audio":
                self.fps = int(self.fps_var.get())
                self.quality = int(self.quality_var.get())
                self.recording_thread = threading.Thread(target=self._record_screen_and_audio)
            else:
                self.recording_thread = threading.Thread(target=self._record_audio_only)
            
            self.recording_thread.daemon = True
            self.recording_thread.start()
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to start recording: {str(e)}")
            self.stop_recording()
    
    def stop_recording(self):
        """Stop recording"""
        self.is_recording = False
        self.record_button.configure(text="Start Recording")
        self.status_var.set("Processing recording...")
    
    def _record_screen_and_audio(self):
        """Record both screen and audio"""
        try:
            screen_size = tuple(pyautogui.size())
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            temp_video = str(Path(tempfile.gettempdir()) / f"temp_video_{timestamp}.avi")
            final_output = str(Path(self.output_dir) / f"recording_{timestamp}.mp4")

            # Initialize video writer with uncompressed format
            fourcc = cv2.VideoWriter_fourcc('I', '4', '2', '0')
            out = cv2.VideoWriter(
                temp_video,
                fourcc,
                self.fps,
                screen_size,
                isColor=True
            )

            if not out.isOpened():
                raise Exception("Failed to create video writer")

            # Start audio recording
            audio_thread = threading.Thread(target=self._record_audio)
            audio_thread.daemon = True
            audio_thread.start()

            frame_interval = 1.0 / self.fps
            next_frame_time = time.time()
            frames_captured = 0

            self.status_var.set("Recording started...")

            while self.is_recording:
                current_time = time.time()
                
                if current_time >= next_frame_time:
                    # Capture screenshot using PIL for better performance
                    screenshot = pyautogui.screenshot()
                    frame = np.array(screenshot)
                    
                    # Convert from RGB to BGR
                    frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
                    
                    # Write frame
                    out.write(frame)
                    
                    frames_captured += 1
                    next_frame_time = current_time + frame_interval

                    if frames_captured % 30 == 0:
                        self.status_var.set(f"Recording... Frames: {frames_captured}")

                # Prevent excessive CPU usage
                remaining_time = next_frame_time - time.time()
                if remaining_time > 0:
                    time.sleep(remaining_time)

        except Exception as e:
            messagebox.showerror("Recording Error", f"Screen recording failed: {str(e)}")
            self.is_recording = False
            return

        finally:
            out.release()
            if os.path.exists(temp_video) and os.path.getsize(temp_video) > 0:
                self._merge_audio_video(temp_video, final_output)
            else:
                self.status_var.set("Recording failed - no video data captured")

    def _merge_audio_video(self, video_path, final_output):
        """Merge audio and video files using FFmpeg subprocess"""
        try:
            # Save audio data
            audio_data = []
            while not self.audio_queue.empty():
                audio_data.append(self.audio_queue.get())

            temp_audio = None

            if audio_data:
                # Save audio to temporary WAV file
                audio_data = np.concatenate(audio_data)
                temp_audio = tempfile.mktemp(suffix='.wav')
                sf.write(temp_audio, audio_data, self.sample_rate)

            # Prepare FFmpeg command
            ffmpeg_cmd = ['ffmpeg', '-y']
            
            # Add video input
            ffmpeg_cmd.extend(['-i', video_path])
            
            # Add audio input if available
            if temp_audio:
                ffmpeg_cmd.extend(['-i', temp_audio])

            # Add encoding parameters
            ffmpeg_cmd.extend([
                '-c:v', 'libx264',
                '-preset', 'veryfast',
                '-pix_fmt', 'yuv420p',
                '-crf', '23',
            ])

            # Add audio parameters if available
            if temp_audio:
                ffmpeg_cmd.extend([
                    '-c:a', 'aac',
                    '-b:a', '128k'
                ])

            # Add output file
            ffmpeg_cmd.append(final_output)

            # Run FFmpeg
            process = subprocess.Popen(
                ffmpeg_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            
            # Wait for completion and get output
            stdout, stderr = process.communicate()

            # Clean up temporary files
            if temp_audio and os.path.exists(temp_audio):
                os.remove(temp_audio)
            if os.path.exists(video_path):
                os.remove(video_path)

            if process.returncode == 0 and os.path.exists(final_output):
                self.status_var.set(f"Recording saved to: {final_output}")
            else:
                error_msg = stderr.decode() if stderr else "Unknown error"
                raise Exception(f"FFmpeg processing failed: {error_msg}")

        except Exception as e:
            messagebox.showerror("Error", f"Failed to process recording: {str(e)}")
            # Try to save the raw video if processing fails
            if os.path.exists(video_path):
                try:
                    backup_path = video_path.replace('.avi', '_backup.avi')
                    os.rename(video_path, backup_path)
                    self.status_var.set(f"Raw video saved to: {backup_path}")
                except:
                    self.status_var.set("Failed to save recording")

    
    def _record_audio_only(self):
        """Record audio only"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.audio_file = str(Path(self.output_dir) / f"audio_{timestamp}.wav")
        
        try:
            with sd.InputStream(channels=self.channels,
                              samplerate=self.sample_rate,
                              callback=self._audio_callback):
                while self.is_recording:
                    time.sleep(0.1)
            
            # Save audio data
            audio_data = []
            while not self.audio_queue.empty():
                audio_data.append(self.audio_queue.get())
            
            if audio_data:
                audio_data = np.concatenate(audio_data)
                sf.write(self.audio_file, audio_data, self.sample_rate)
                self.status_var.set(f"Audio saved to: {self.audio_file}")
            else:
                self.status_var.set("No audio data recorded")
                
        except Exception as e:
            messagebox.showerror("Error", f"Audio recording failed: {str(e)}")
            self.status_var.set("Recording failed")
    
    def _record_audio(self):
        """Record audio for video recording"""
        try:
            with sd.InputStream(channels=self.channels,
                              samplerate=self.sample_rate,
                              callback=self._audio_callback):
                while self.is_recording:
                    time.sleep(0.1)
        except Exception as e:
            messagebox.showerror("Audio Error", f"Audio recording failed: {str(e)}")
    
    def _audio_callback(self, indata, frames, time, status):
        """Audio recording callback"""
        if status:
            print(status)
        self.audio_queue.put(indata.copy())

    
    def _validate_settings(self):
        """Validate all settings before recording"""
        try:
            # Validate output directory
            if not self.output_dir:
                raise ValueError("Output directory not specified")
            
            # Create directory if it doesn't exist
            Path(self.output_dir).mkdir(parents=True, exist_ok=True)
            
            # Check write permissions
            if not os.access(self.output_dir, os.W_OK):
                raise ValueError("Output directory is not writable")
            
            # Validate FPS if screen recording
            if self.mode_var.get() == "Screen & Audio":
                fps = int(self.fps_var.get())
                if not 1 <= fps <= 60:
                    raise ValueError("FPS must be between 1 and 60")
                
                quality = int(self.quality_var.get())
                if not 1 <= quality <= 100:
                    raise ValueError("Quality must be between 1 and 100")
            
            # Validate audio device if audio is enabled
            if self.audio_enabled:
                if not self.audio_device_var.get():
                    raise ValueError("No audio device selected")
            
            return True
            
        except ValueError as e:
            messagebox.showerror("Validation Error", str(e))
            return False
        except Exception as e:
            messagebox.showerror("Error", f"Settings validation failed: {str(e)}")
            return False
    
    def _cleanup(self):
        """Clean up resources before closing"""
        try:
            self.preview_active = False
            if hasattr(self, 'preview_thread'):
                self.preview_thread.join(timeout=1.0)
            
            # Stop any ongoing recording
            if self.is_recording:
                self.stop_recording()
                if hasattr(self, 'recording_thread'):
                    self.recording_thread.join(timeout=2.0)
            
            # Clean up temporary files
            temp_dir = tempfile.gettempdir()
            for file in os.listdir(temp_dir):
                if file.startswith('screen_recorder_temp'):
                    try:
                        os.remove(os.path.join(temp_dir, file))
                    except:
                        pass
                        
        except Exception as e:
            print(f"Cleanup error: {str(e)}")
    
    def run(self):
        """Start the GUI application"""
        try:
            # Register cleanup on window close
            self.root.protocol("WM_DELETE_WINDOW", self._on_closing)
            self.root.mainloop()
        except Exception as e:
            messagebox.showerror("Error", f"Application error: {str(e)}")
            self._cleanup()
    
    def _on_closing(self):
        """Handle window closing"""
        if self.is_recording:
            if messagebox.askyesno("Quit", "Recording is in progress. Stop recording and quit?"):
                self._cleanup()
                self.root.destroy()
        else:
            self._cleanup()
            self.root.destroy()

if __name__ == "__main__":
    try:
        app = ScreenRecorderGUI()
        app.run()
    except Exception as e:
        messagebox.showerror("Fatal Error", f"Failed to start application: {str(e)}")
        