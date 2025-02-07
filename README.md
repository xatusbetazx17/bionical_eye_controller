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

class BionicEyeController:
    """
    A conceptual controller for a bionic eye device that supports multiple features.
    This class abstracts the communication interface (USB or wireless). If the expected
    hardware is not found, it falls back to simulation.
    """

    def __init__(self, connection_type='usb', port=None):
        self.connection_type = connection_type

        if self.connection_type == 'usb':
            if usb is None:
                print("USB module not available; simulating USB connection.")
                self.device = None
            else:
                self.device = usb.core.find(idVendor=0x1234, idProduct=0x5678)
                if self.device is None:
                    print("USB device not found. Simulating USB connection.")
                    self.device = None
                else:
                    try:
                        self.device.set_configuration()
                        print("USB device initialized.")
                    except Exception as e:
                        print("Failed to set USB configuration. Simulating USB connection:", e)
                        self.device = None
        elif self.connection_type == 'wireless':
            if serial is None:
                print("Serial module not available; simulating wireless connection.")
                self.ser = None
            else:
                if port is None:
                    port = '/dev/ttyUSB0'
                try:
                    self.ser = serial.Serial(port, baudrate=115200, timeout=1)
                    print("Wireless device initialized on port:", port)
                except Exception as e:
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
                # Example: self.device.write(endpoint, command.encode('ascii'))
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

def eye_control_interface(controller):
    """
    Displays a live camera feed with an overlaid eye-controlled UI.
    Four buttons (Change Color, Zoom, Night Vision, Diagnostics) are drawn on the right.
    If the user’s gaze (detected via a Haar cascade) dwells over a button for 2 seconds,
    the corresponding command is triggered.
    Press 'q' to exit the interface.
    """
    if cv2 is None or np is None:
        print("Camera interface libraries not available. Cannot start eye control interface.")
        return

    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("Cannot open camera for eye control interface.")
        return

    # Load Haar cascade for eye detection
    eye_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_eye.xml")

    # Define UI buttons: label and rectangle (x, y, width, height)
    buttons = {
        "Change Color": (480, 50, 150, 50),
        "Zoom": (480, 120, 150, 50),
        "Night Vision": (480, 190, 150, 50),
        "Diagnostics": (480, 260, 150, 50)
    }
    dwell_threshold = 2.0  # seconds required to trigger a button
    dwell_times = {label: None for label in buttons}

    # State variables for cycling options
    color_options = ["#FF0000", "#00FF00", "#0000FF", "#FFFF00"]
    current_color_index = 0
    zoom_options = [1.0, 1.5, 2.0]
    current_zoom_index = 0
    night_vision_on = False
    diagnostics_message = ""
    diagnostics_timestamp = 0

    while True:
        ret, frame = cap.read()
        if not ret:
            print("Failed to capture frame from camera.")
            break

        # Flip frame horizontally (mirror effect)
        frame = cv2.flip(frame, 1)

        # Convert to grayscale for eye detection
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        eyes = eye_cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(30, 30))
        eye_center = None
        if len(eyes) > 0:
            cx = sum([ex + ew / 2 for (ex, ey, ew, eh) in eyes]) / len(eyes)
            cy = sum([ey + eh / 2 for (ex, ey, ew, eh) in eyes]) / len(eyes)
            eye_center = (int(cx), int(cy))
            cv2.circle(frame, eye_center, 5, (0, 255, 0), -1)

        current_time = time.time()
        # Process each button
        for label, (x, y, w, h) in buttons.items():
            # Draw button border
            cv2.rectangle(frame, (x, y), (x + w, y + h), (50, 50, 50), 2)
            # Check if eye center is within this button
            if eye_center is not None and x <= eye_center[0] <= x + w and y <= eye_center[1] <= y + h:
                if dwell_times[label] is None:
                    dwell_times[label] = current_time
                dwell_duration = current_time - dwell_times[label]
                # Draw progress indicator on the button
                progress_width = int((dwell_duration / dwell_threshold) * w)
                progress_width = min(progress_width, w)
                cv2.rectangle(frame, (x, y), (x + progress_width, y + h), (0, 255, 0), -1)
                # Trigger action if dwell time exceeds threshold
                if dwell_duration >= dwell_threshold:
                    print(f"Action triggered for: {label}")
                    if label == "Change Color":
                        current_color_index = (current_color_index + 1) % len(color_options)
                        controller.change_iris_color(color_options[current_color_index])
                    elif label == "Zoom":
                        current_zoom_index = (current_zoom_index + 1) % len(zoom_options)
                        controller.set_zoom_level(zoom_options[current_zoom_index])
                    elif label == "Night Vision":
                        night_vision_on = not night_vision_on
                        controller.enable_night_vision(night_vision_on)
                    elif label == "Diagnostics":
                        diagnostics_message = controller.system_diagnostics()
                        diagnostics_timestamp = current_time
                    dwell_times[label] = None  # reset dwell timer
            else:
                dwell_times[label] = None

            # Draw button label
            cv2.putText(frame, label, (x + 5, y + 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 0), 2)

        # Display diagnostics message for 3 seconds if available
        if diagnostics_message and (current_time - diagnostics_timestamp) < 3:
            cv2.putText(frame, diagnostics_message, (50, 450), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)
        elif current_time - diagnostics_timestamp >= 3:
            diagnostics_message = ""

        cv2.imshow("Eye Control Interface", frame)
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    cap.release()
    cv2.destroyAllWindows()

if __name__ == '__main__':
    # Initialize the bionic eye controller (in simulation mode if hardware is missing)
    controller = BionicEyeController(connection_type='usb')
    # Start the eye-controlled interface
    eye_control_interface(controller)


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

