# Bionic Eye Controller

A conceptual Python program for controlling a simulated bionic eye device with augmented features such as changing iris color, zoom, night vision, augmented reality overlays, and more. This project demonstrates auto-installation of dependencies (using the `--break-system-packages` flag) and simulates USB/wireless communication with the device.

> **Warning:**  
> This code is purely conceptual and for educational purposes only. It is not intended for production use or interfacing with actual medical devices. It is highly recommended to use a virtual environment for development to avoid system-wide package issues.

## Features

- **Dynamic Iris Color:** Change the iris color using commands.
- **Optical Zoom:** Adjust the zoom level.
- **Night Vision:** Toggle night vision mode.
- **Augmented Reality Overlays:** Activate AR overlays.
- **Custom Functions:** Execute additional custom commands.
- **Auto-Installation:** Automatically installs required Python packages (`pyusb` and `pyserial`) if not found (using `--break-system-packages`).
- **Simulated USB/Wireless Communication:** Simulates device communication if the required modules are not available.

## Requirements

- Python 3.6+
- (Recommended) A virtual environment to avoid conflicts with system-wide packages

## Installation

1. **Clone the repository:**

   ```bash
   git clone https://github.com/xatusbetazx17/Bionic-Eye-Controller.git
   cd Bionic-Eye-Controller
(Optional) Create and activate a virtual environment:

bash
Copy
python -m venv venv
source venv/bin/activate   # On Windows, use: venv\Scripts\activate
Run the script:

The script will try to install any missing dependencies automatically. If your environment is externally managed, the script uses the --break-system-packages flag.
Note: It is recommended to use a virtual environment.

bash
Copy
python bionic_eye_controller.py
Usage
Once running, you will see a command-line interface. Type help for a list of available commands. Here are some examples:

Change Iris Color:

plaintext
Copy
>> change_color #FF5733
Set Optical Zoom:

plaintext
Copy
>> zoom 2.5
Toggle Night Vision:

plaintext
Copy
>> night on
>> night off
Activate AR Overlay:

plaintext
Copy
>> ar YourOverlayDataHere
Run System Diagnostics:

plaintext
Copy
>> diag
Run a Custom Function:

plaintext
Copy
>> custom FUNCTION_CODE
Exit the Program:

plaintext
Copy
>> exit
Repository Structure
bionic_eye_controller.py:
The main Python script that implements the bionic eye controller with all features and auto-installation of dependencies.

README.md:
This file, explaining the project.

.gitignore:
Recommended to ignore environment files and caches. See the file content below.

.gitignore
gitignore
Copy
# Ignore Python cache files and virtual environments
__pycache__/
*.pyc
venv/
License
This project is provided for educational purposes only.
MIT License

Disclaimer:
This is a conceptual project. In a real-world scenario, interfacing with bionic implants involves rigorous testing, security measures, and adherence to strict medical and safety standards.

python
Copy


### bionic_eye_controller.py

~~~
#!/usr/bin/env python3
import subprocess
import sys
import threading
import time

def install_package(package_name):
    """
    Attempt to install a package using pip with the --break-system-packages flag.
    WARNING: Overriding system package management may have unintended side effects.
    """
    try:
        print(f"Attempting to install {package_name}...")
        subprocess.check_call([
            sys.executable, "-m", "pip", "install", package_name, "--break-system-packages"
        ])
        print(f"{package_name} installed successfully.")
    except subprocess.CalledProcessError as e:
        print(f"Failed to install {package_name}: {e}")

# Auto-install and import PyUSB
try:
    import usb.core
    import usb.util
except ImportError:
    install_package("pyusb")
    try:
        import usb.core
        import usb.util
    except ImportError as e:
        print("PyUSB not installed. USB functionality will be simulated.", e)
        usb = None

# Auto-install and import PySerial
try:
    import serial
except ImportError:
    install_package("pyserial")
    try:
        import serial
    except ImportError as e:
        print("PySerial not installed. Wireless functionality will be simulated.", e)
        serial = None

# Auto-install and import OpenCV (cv2)
try:
    import cv2
except ImportError:
    install_package("opencv-python")
    try:
        import cv2
    except ImportError as e:
        print("cv2 (opencv-python) not installed. Camera interface will be simulated.", e)
        cv2 = None

# Auto-install and import numpy
try:
    import numpy as np
except ImportError:
    install_package("numpy")
    try:
        import numpy as np
    except ImportError as e:
        print("numpy not installed. Camera boot screen will be simulated.", e)
        np = None

# Auto-install and import MediaPipe for hand tracking
try:
    import mediapipe as mp
except ImportError:
    install_package("mediapipe")
    try:
        import mediapipe as mp
    except ImportError as e:
        print("mediapipe not installed. Hand control interface will be simulated.", e)
        mp = None

class BionicEyeController:
    """
    A conceptual controller for a bionic eye device that supports multiple features.
    This class abstracts the communication interface (USB or wireless). If the expected
    hardware is not found, it falls back to simulation.
    """
    def __init__(self, connection_type='usb', port=None, debug=True):
        self.connection_type = connection_type
        self.debug = debug

        if self.connection_type == 'usb':
            if usb is None:
                if self.debug:
                    print("USB module not available; simulating USB connection.")
                self.device = None
            else:
                self.device = usb.core.find(idVendor=0x1234, idProduct=0x5678)
                if self.device is None:
                    if self.debug:
                        print("USB device not found. Simulating USB connection.")
                    self.device = None
                else:
                    try:
                        self.device.set_configuration()
                        if self.debug:
                            print("USB device initialized.")
                    except Exception as e:
                        if self.debug:
                            print("Failed to set USB configuration. Simulating USB connection:", e)
                        self.device = None
        elif self.connection_type == 'wireless':
            if serial is None:
                if self.debug:
                    print("Serial module not available; simulating wireless connection.")
                self.ser = None
            else:
                if port is None:
                    port = '/dev/ttyUSB0'
                try:
                    self.ser = serial.Serial(port, baudrate=115200, timeout=1)
                    if self.debug:
                        print("Wireless device initialized on port:", port)
                except Exception as e:
                    if self.debug:
                        print("Wireless device initialization failed. Simulating wireless connection:", e)
                    self.ser = None
        else:
            raise ValueError("Unsupported connection type: " + self.connection_type)

    def send_command(self, command: str):
        """
        Sends a command string to the bionic eye device.
        """
        if self.connection_type == 'usb':
            if self.device is None:
                print(f"[USB Simulation] Command sent: {command}")
            else:
                print(f"[USB] Sending command: {command}")
        elif self.connection_type == 'wireless':
            if self.ser is None:
                print(f"[Wireless Simulation] Command sent: {command}")
            else:
                self.ser.write((command + "\n").encode('ascii'))
                print(f"[Wireless] Sending command: {command}")
        else:
            print("Unknown connection type; cannot send command.")

    # --- Feature Methods ---
    def change_iris_color(self, color: str):
        command = f"SET_IRIS_COLOR {color}"
        self.send_command(command)

    def set_zoom_level(self, level: float):
        command = f"SET_ZOOM {level}"
        self.send_command(command)

    def enable_night_vision(self, enable: bool = True):
        command = "NIGHT_VISION ON" if enable else "NIGHT_VISION OFF"
        self.send_command(command)

    def activate_AR_overlay(self, overlay_data: str):
        command = f"ACTIVATE_AR {overlay_data}"
        self.send_command(command)

    def run_custom_function(self, function_code: str):
        command = f"RUN_CUSTOM {function_code}"
        self.send_command(command)

    def system_diagnostics(self):
        command = "DIAGNOSTICS"
        self.send_command(command)
        return "Diagnostics: All systems nominal."

    def update_firmware(self):
        command = "UPDATE_FIRMWARE"
        self.send_command(command)
        return "Firmware update initiated."

def hand_control_interface(controller):
    """
    Displays a live camera feed (simulating natural vision) with a toggleable hand-controlled menu.

    - A small toggle region is drawn in the top-right corner. When the user holds their index
      finger (detected via MediaPipe Hands) in that region for 2 seconds, the menu is toggled.
    - When open, a scrollable vertical menu (with options such as Change Color, Zoom, Night Vision,
      Diagnostics, Update) appears. The user can hover over an option with their index finger; if the pointer
      dwells for 1.5 seconds, the option is selected and the corresponding command is executed.
    - The menu then hides, allowing the user to continue with a natural view.
    - Feedback messages are shown on screen after a change is made and then disappear after a few seconds.
    - The pointer is smoothed for less jittery movement.

    Press 'q' to exit the interface.
    """
    if cv2 is None or np is None or mp is None:
        print("Necessary libraries not available. Cannot start hand control interface.")
        return

    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("Cannot open camera for hand control interface.")
        return

    mp_hands = mp.solutions.hands
    hands = mp_hands.Hands(max_num_hands=1)
    mp_drawing = mp.solutions.drawing_utils

    menu_open = False
    menu_toggle_dwell = None
    menu_toggle_threshold = 2.0  # seconds required to toggle menu
    # Toggle region: a circle in the top-right corner
    frame_width, frame_height = 640, 480  # assume these dimensions; adjust if needed
    toggle_region_center = (frame_width - 40, 40)
    toggle_region_radius = 30

    # Define menu options (vertical list)
    menu_options = ["Change Color", "Zoom", "Night Vision", "Diagnostics", "Update"]
    menu_x = 50
    menu_y = 100
    menu_width = 200
    option_height = 40
    option_dwell_threshold = 1.5  # seconds dwell to select an option
    option_dwell_times = {option: None for option in menu_options}

    # Variables for displaying feedback messages
    feedback_message = ""
    feedback_timestamp = 0
    feedback_duration = 3.0  # seconds to display the feedback

    smoothed_pointer = None
    alpha = 0.3  # smoothing factor

    while True:
        ret, frame = cap.read()
        if not ret:
            print("Failed to capture frame from camera.")
            break

        frame = cv2.flip(frame, 1)  # mirror the view
        frame_h, frame_w, _ = frame.shape

        # Process hand landmarks using MediaPipe
        image_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = hands.process(image_rgb)
        pointer = None

        if results.multi_hand_landmarks:
            for hand_landmarks in results.multi_hand_landmarks:
                # Draw landmarks for debugging
                mp_drawing.draw_landmarks(frame, hand_landmarks, mp_hands.HAND_CONNECTIONS)
                # Use the index finger tip (landmark 8) as the pointer
                x = hand_landmarks.landmark[8].x * frame_w
                y = hand_landmarks.landmark[8].y * frame_h
                pointer = (int(x), int(y))
                break  # use first detected hand

        # Smooth the pointer position
        if pointer is not None:
            if smoothed_pointer is None:
                smoothed_pointer = pointer
            else:
                smoothed_pointer = (
                    int(alpha * pointer[0] + (1 - alpha) * smoothed_pointer[0]),
                    int(alpha * pointer[1] + (1 - alpha) * smoothed_pointer[1])
                )
            cv2.circle(frame, smoothed_pointer, 5, (0, 255, 0), -1)
        else:
            smoothed_pointer = None

        current_time = time.time()

        # Draw toggle region for the menu (top-right)
        cv2.circle(frame, toggle_region_center, toggle_region_radius, (200, 200, 200), 2)
        cv2.putText(frame, "Menu", (toggle_region_center[0] - 30, toggle_region_center[1] + 5),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 1)

        # Check if pointer is inside the toggle region
        if smoothed_pointer is not None:
            dx = smoothed_pointer[0] - toggle_region_center[0]
            dy = smoothed_pointer[1] - toggle_region_center[1]
            dist = (dx*dx + dy*dy) ** 0.5
            if dist <= toggle_region_radius:
                if menu_toggle_dwell is None:
                    menu_toggle_dwell = current_time
                dwell = current_time - menu_toggle_dwell
                # Draw progress (arc) on the toggle region
                progress_angle = int((dwell / menu_toggle_threshold) * 360)
                cv2.ellipse(frame, toggle_region_center, (toggle_region_radius, toggle_region_radius), 0, 0, progress_angle, (0, 255, 0), 2)
                if dwell >= menu_toggle_threshold:
                    menu_open = not menu_open
                    menu_toggle_dwell = None
                    option_dwell_times = {option: None for option in menu_options}
            else:
                menu_toggle_dwell = None

        # If menu is open, display the scrollable menu overlay
        if menu_open:
            # Draw a semi-transparent rectangle as menu background
            overlay = frame.copy()
            cv2.rectangle(overlay, (menu_x, menu_y), (menu_x + menu_width, menu_y + len(menu_options) * option_height), (50, 50, 50), -1)
            cv2.addWeighted(overlay, 0.6, frame, 0.4, 0, frame)

            # Draw each menu option and check for pointer dwell
            for idx, option in enumerate(menu_options):
                ox = menu_x
                oy = menu_y + idx * option_height
                cv2.rectangle(frame, (ox, oy), (ox + menu_width, oy + option_height), (100, 100, 100), 1)
                cv2.putText(frame, option, (ox + 5, oy + 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
                # Check if pointer is over the option
                if smoothed_pointer is not None and ox <= smoothed_pointer[0] <= ox + menu_width and oy <= smoothed_pointer[1] <= oy + option_height:
                    if option_dwell_times[option] is None:
                        option_dwell_times[option] = current_time
                    option_dwell = current_time - option_dwell_times[option]
                    prog_width = int((option_dwell / option_dwell_threshold) * menu_width)
                    prog_width = min(prog_width, menu_width)
                    cv2.rectangle(frame, (ox, oy), (ox + prog_width, oy + option_height), (0, 255, 0), -1)
                    if option_dwell >= option_dwell_threshold:
                        print(f"Option selected: {option}")
                        if option == "Change Color":
                            controller.change_iris_color("#FF0000")  # You can add cycling logic here
                            feedback_message = "Iris color changed to #FF0000"
                        elif option == "Zoom":
                            controller.set_zoom_level(2.0)
                            feedback_message = "Zoom set to 2.0"
                        elif option == "Night Vision":
                            controller.enable_night_vision(True)
                            feedback_message = "Night vision enabled"
                        elif option == "Diagnostics":
                            diag = controller.system_diagnostics()
                            print(diag)
                            feedback_message = diag
                        elif option == "Update":
                            upd = controller.update_firmware()
                            print(upd)
                            feedback_message = upd
                        menu_open = False  # Close menu after selection
                        option_dwell_times = {opt: None for opt in menu_options}
                        feedback_timestamp = current_time
                else:
                    option_dwell_times[option] = None

        # Display feedback message (if any) for a limited duration
        if feedback_message and (current_time - feedback_timestamp) < feedback_duration:
            cv2.putText(frame, feedback_message, (50, 80), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)
        elif current_time - feedback_timestamp >= feedback_duration:
            feedback_message = ""

        cv2.imshow("Hand Control Interface", frame)
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    cap.release()
    cv2.destroyAllWindows()

if __name__ == '__main__':
    # Initialize the bionic eye controller (simulation mode if hardware is missing)
    # Set debug=False to suppress simulation messages.
    controller = BionicEyeController(connection_type='usb', debug=False)
    # Start the hand-controlled interface with a toggleable, scrollable menu
    hand_control_interface(controller)

~~~
        
## .gitignore

Copy

# Ignore Python cache files and virtual environments
__pycache__/
*.pyc
venv/

## How to Create and Push the Repository
Create a new repository on GitHub with the name Bionic-Eye-Controller under your account xatusbetazx17.

Clone the repository locally:

bash
Copy
~~~
git clone https://github.com/xatusbetazx17/Bionic-Eye-Controller.git
cd Bionic-Eye-Controller
~~~
Add the files:
Create the files README.md, bionic_eye_controller.py, and .gitignore with the content provided above.

Commit and push:

bash
Copy
~~~
git add .
git commit -m "Initial commit: Add bionic eye controller project with auto-install functionality"
git push origin main
~~~
## License 

MIT License

Copyright (c) 2025 xatusbetazx17

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.

