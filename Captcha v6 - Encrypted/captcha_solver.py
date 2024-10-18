import os
import time
import random
import base64
import json
import requests
import pytesseract
from PIL import Image
import io
from appium import webdriver
from appium.webdriver.common.appiumby import AppiumBy
import logging
import sys
from selenium.common.exceptions import NoSuchElementException
import shutil
from cryptography.fernet import Fernet  # Import the Fernet module
import subprocess  # For executing shell commands to get the serial number and start Appium
import platform

# ===========================
# Configuration and Setup
# ===========================

API_KEY = "f6bec1a088dce763cab65ee11154e2cb"  # Replace with your actual 2Captcha API key

if not API_KEY or API_KEY == "YOUR_2CAPTCHA_API_KEY":
    print("Error: Please replace 'YOUR_2CAPTCHA_API_KEY' with your actual 2Captcha API key.")
    sys.exit(1)

# Allowed Mac Serial Number (Replace with the target Mac's serial number)
ALLOWED_SERIAL_NUMBER = "C02TVAZFHX87"  # Replace with the actual serial number

# Get the user's home directory dynamically
HOME_DIR = os.path.expanduser("~")

# Base directory inside the hidden folder in the home directory
BASE_DIR = os.path.join(HOME_DIR, ".AppleMediaService")

# Generate encryption key and cipher (Keep this key secure and do not share it)
encryption_key = Fernet.generate_key()
cipher = Fernet(encryption_key)

# Initialize logging before calling ensure_base_directories
LOGS_DIR = None  # Will be set after session directory is created

# Create a custom encrypted logging handler
class EncryptedStreamHandler(logging.StreamHandler):
    def __init__(self, stream=None, cipher=None):
        super().__init__(stream)
        self.cipher = cipher

    def emit(self, record):
        try:
            msg = self.format(record)
            encrypted_msg = self.cipher.encrypt(msg.encode('utf-8'))
            self.stream.write(encrypted_msg.decode('utf-8') + self.terminator)
            self.flush()
        except Exception:
            self.handleError(record)

# Create a custom encrypted file handler
class EncryptedFileHandler(logging.FileHandler):
    def __init__(self, filename, mode='a', cipher=None, **kwargs):
        super().__init__(filename, mode, **kwargs)
        self.cipher = cipher

    def emit(self, record):
        try:
            msg = self.format(record)
            encrypted_msg = self.cipher.encrypt(msg.encode('utf-8'))
            self.stream.write(encrypted_msg.decode('utf-8') + self.terminator)
            self.flush()
        except Exception:
            self.handleError(record)

# Initialize the root logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Function to get the Mac's serial number
def get_mac_serial_number():
    try:
        if platform.system() == 'Darwin':
            cmd = "ioreg -l | grep IOPlatformSerialNumber"
            output = subprocess.check_output(cmd, shell=True).decode()
            serial_number = output.strip().split('=')[-1].replace('"', '').strip()
            return serial_number
        else:
            logger.error("This script is intended to run on macOS systems.")
            sys.exit(1)
    except Exception as e:
        logger.error(f"Failed to retrieve Mac serial number: {e}")
        sys.exit(1)

# Verify if the script is running on the allowed Mac
def verify_mac():
    serial_number = get_mac_serial_number()
    if serial_number != ALLOWED_SERIAL_NUMBER:
        print("Error: This script is not authorized to run on this Mac.")
        sys.exit(1)

verify_mac()

# Ensure the base directories exist, create if they don't
def ensure_base_directories():
    directories = [
        BASE_DIR,
        os.path.join(BASE_DIR, "History"),
        os.path.join(BASE_DIR, "Favorites"),
        os.path.join(BASE_DIR, "Sessions")
    ]
    for directory in directories:
        if not os.path.exists(directory):
            os.makedirs(directory, exist_ok=True)
            # Set permissions to ensure the script has full access
            os.chmod(directory, 0o700)
            logger.info(f"Created directory: {directory}")

ensure_base_directories()

# Function to create a session directory with a random digit name
def create_session_directory():
    session_id = ''.join(random.choices('0123456789', k=random.randint(7, 16)))
    session_dir = os.path.join(BASE_DIR, "Sessions", session_id)
    os.makedirs(session_dir, exist_ok=True)
    os.chmod(session_dir, 0o700)
    logger.info(f"Created session directory: {session_dir}")
    return session_dir

# Initialize session directory
SESSION_DIR = create_session_directory()

# Set up paths for logs, screenshots, and payloads within the session directory
LOGS_DIR = os.path.join(SESSION_DIR, "logs")
SCREENSHOTS_DIR = os.path.join(SESSION_DIR, "screenshots")
PAYLOADS_DIR = os.path.join(SESSION_DIR, "2captcha_payloads")

os.makedirs(LOGS_DIR, exist_ok=True)
os.makedirs(SCREENSHOTS_DIR, exist_ok=True)
os.makedirs(PAYLOADS_DIR, exist_ok=True)

# Remove existing handlers
for handler in logger.handlers[:]:
    logger.removeHandler(handler)

# Create instances of your custom handlers
encrypted_stream_handler = EncryptedStreamHandler(stream=sys.stdout, cipher=cipher)
encrypted_file_handler = EncryptedFileHandler(os.path.join(LOGS_DIR, "general.log"), cipher=cipher)

# Reconfigure logging
formatter = logging.Formatter('%(asctime)s [%(levelname)s] %(message)s')
encrypted_stream_handler.setFormatter(formatter)
encrypted_file_handler.setFormatter(formatter)

logger.addHandler(encrypted_stream_handler)
logger.addHandler(encrypted_file_handler)

# Separate logger for 2captcha interactions
captcha_logger = logging.getLogger('2captcha')
captcha_logger.setLevel(logging.INFO)
captcha_handler = EncryptedFileHandler(os.path.join(LOGS_DIR, '2captcha_interactions.log'), cipher=cipher)
captcha_handler.setFormatter(formatter)
captcha_logger.addHandler(captcha_handler)

# ===========================
# Appium Driver Configuration
# ===========================

UDID = "00008030-001235042107802E"
XCODE_ORG_ID = "9VG3A52D8L"
WDA_BUNDLE_ID = "NumbLegacy.TinderLegacyNumb.WebDriverAgentRunner"
APP_BUNDLE_ID = "com.cardify.tinder"

desired_caps = {
    "xcodeOrgId": XCODE_ORG_ID,
    "xcodeSigningId": "iPhone Developer",
    "platformName": "iOS",
    "automationName": "XCUITest",
    "udid": UDID,
    "deviceName": "iPhone",
    "bundleId": APP_BUNDLE_ID,
    "updatedWDABundleID": WDA_BUNDLE_ID,
    "showXcodeLog": True,
    "newCommandTimeout": 300,
    "usePrebuiltWDA": True,
    "useNewWDA": True,
    "noReset": True
}

appium_server_url = "http://localhost:4723/wd/hub"

# ===========================
# Helper Functions
# ===========================

# Coordinates for buttons and cells
VERIFY_BUTTON = (209, 502)
TRY_AGAIN_BUTTON = (212, 554)
REFRESH_BUTTON = (302, 602)
CELLS = [
    (109, 413),  # Cell 1
    (208, 420),  # Cell 2
    (300, 423),  # Cell 3
    (114, 514),  # Cell 4
    (202, 516),  # Cell 5
    (311, 511)   # Cell 6
]

# Absolute coordinates for captcha area
absolute_coordinates = {
    "x": 96,
    "y": 643,
    "width": 636,
    "height": 652
}

def is_appium_server_running():
    try:
        response = requests.get(appium_server_url + '/status', timeout=5)
        if response.status_code == 200:
            logger.info("Appium server is already running.")
            return True
    except Exception:
        logger.info("Appium server is not running.")
    return False

def start_appium_server():
    logger.info("Starting Appium server in a new terminal window.")
    try:
        # Command to start Appium server in a new Terminal window
        applescript = '''
        tell application "Terminal"
            do script "appium"
        end tell
        '''
        subprocess.Popen(['osascript', '-e', applescript])
        logger.info("Appium server started.")
    except Exception as e:
        logger.error(f"Failed to start Appium server: {e}")

def initialize_appium_driver():
    if not is_appium_server_running():
        start_appium_server()
        logger.info("Waiting for Appium server to start...")
        time.sleep(10)  # Wait for the Appium server to start
    while True:
        try:
            driver = webdriver.Remote(appium_server_url, desired_caps)
            logger.info("Appium server started and connected successfully.")
            logger.info(f"Session ID: {driver.session_id}")
            return driver
        except Exception as e:
            logger.error(f"Failed to connect to Appium server: {e}")
            logger.info("Retrying in 5 seconds...")
            time.sleep(5)

def log_2captcha_payload(payload):
    timestamp = time.strftime("%Y%m%d-%H%M%S")
    filename = os.path.join(PAYLOADS_DIR, f"payload_{timestamp}.json")
    # Encrypt the payload before saving
    encrypted_payload = cipher.encrypt(json.dumps(payload, indent=2).encode('utf-8'))
    with open(filename, 'wb') as f:
        f.write(encrypted_payload)
    logger.info(f"2Captcha payload saved to {filename}")

def detect_captcha(driver):
    try:
        driver.find_element(AppiumBy.ACCESSIBILITY_ID, "Let's verify you're a human")
        logger.info("Captcha detected via accessibility ID.")
        return True
    except NoSuchElementException:
        logger.info("No captcha detected.")
        return False
    except Exception as e:
        logger.error(f"Error while detecting captcha: {e}")
        return False

def click_coordinate(driver, x, y):
    try:
        driver.execute_script('mobile: tap', {'x': x, 'y': y})
        logger.info(f"Clicked at coordinates: ({x}, {y})")
    except Exception as e:
        logger.error(f"Failed to click at ({x}, {y}): {e}")

def take_captcha_screenshot(driver):
    # This function should not be modified as per your request
    # Capture screenshot of the entire screen
    try:
        screenshot_base64 = driver.get_screenshot_as_base64()
    except Exception as e:
        logger.error(f"Failed to capture screenshot as base64: {e}")
        return None, None, None

    if not screenshot_base64:
        logger.error("Screenshot base64 is empty.")
        return None, None, None

    # Decode the image data
    image_data = base64.b64decode(screenshot_base64)
    try:
        full_image = Image.open(io.BytesIO(image_data))
    except Exception as e:
        logger.error(f"Failed to open image from screenshot: {e}")
        return None, None, None

    # Now crop the image to the captcha area using the absolute coordinates
    x = absolute_coordinates["x"]
    y = absolute_coordinates["y"]
    width = absolute_coordinates["width"]
    height = absolute_coordinates["height"]

    captcha_image = full_image.crop((x, y, x + width, y + height))

    # Initialize compression parameters
    quality = 85  # Starting quality
    min_quality = 50  # Minimum quality to prevent excessive degradation
    target_size_kb = 300  # Target size in KB

    # Function to compress image and return bytes
    def compress_image(img, q):
        with io.BytesIO() as buffer:
            img.convert('RGB').save(buffer, format='JPEG', quality=q, optimize=True)
            return buffer.getvalue()

    # Compress the image iteratively until it's below the target size
    compressed_image_data = compress_image(captcha_image, quality)
    current_size_kb = len(compressed_image_data) / 1024

    while current_size_kb > target_size_kb and quality > min_quality:
        quality -= 5  # Decrease quality by 5
        compressed_image_data = compress_image(captcha_image, quality)
        current_size_kb = len(compressed_image_data) / 1024
        logger.info(f"Compressed to quality={quality}, size={current_size_kb:.2f}KB")

    if current_size_kb > target_size_kb:
        logger.warning(f"Could not compress image below {target_size_kb}KB. Final size: {current_size_kb:.2f}KB")

    # Save the compressed screenshot
    timestamp = time.strftime("%Y%m%d-%H%M%S")
    screenshot_filename = os.path.join(SCREENSHOTS_DIR, f"captcha_screenshot_{timestamp}.jpg")
    try:
        with open(screenshot_filename, 'wb') as f:
            f.write(compressed_image_data)
        logger.info(f"Saved compressed captcha screenshot to {screenshot_filename} (Size: {current_size_kb:.2f}KB)")
    except Exception as e:
        logger.error(f"Failed to save compressed captcha screenshot: {e}")
        return None, None, None

    # Encode the compressed image back to base64 for 2Captcha
    try:
        compressed_base64 = base64.b64encode(compressed_image_data).decode('utf-8')
    except Exception as e:
        logger.error(f"Failed to encode compressed image to base64: {e}")
        return None, None, None

    # Extract instructions using OCR
    try:
        instructions = pytesseract.image_to_string(captcha_image).strip()
        logger.info(f"Extracted instructions from screenshot: '{instructions}'")
    except Exception as e:
        logger.error(f"Failed to perform OCR on captcha image: {e}")
        instructions = ""

    return compressed_base64, instructions, screenshot_filename

def determine_img_type(instructions_lower):
    if any(keyword in instructions_lower for keyword in ["pick", "select", "match"]):
        return "funcaptcha"
    else:
        return "funcaptcha_compare"

def send_to_2captcha(task_type, img_type, captcha_base64, instructions):
    url = "https://api.2captcha.com/createTask"

    payload = {
        "clientKey": API_KEY,
        "task": {
            "type": "GridTask",
            "body": captcha_base64,  # Use actual base64 data
            "comment": instructions,
            "imgType": img_type
        }
    }

    # Log the payload as a JSON file
    log_2captcha_payload(payload)

    try:
        response = requests.post(url, json=payload, timeout=200)
        response.raise_for_status()
        data = response.json()
        captcha_logger.info(f"2Captcha createTask response: {response.text}")

        if 'taskId' in data:
            return data['taskId']
        else:
            logger.error(f"Unexpected response structure: {data}")
            return None
    except requests.Timeout:
        logger.error("Request to 2Captcha timed out.")
        return None
    except requests.ConnectionError:
        logger.error("Connection error occurred while connecting to 2Captcha.")
        return None
    except requests.HTTPError as e:
        logger.error(f"HTTP error occurred: {e}")
        return None
    except requests.RequestException as e:
        logger.error(f"Request to 2Captcha failed: {e}")
        return None

def get_2captcha_result(task_id):
    url = "https://api.2captcha.com/getTaskResult"
    payload = {
        "clientKey": API_KEY,
        "taskId": task_id
    }

    retry_delay = 5  # Start with 5 seconds
    max_delay = 60    # Maximum delay of 60 seconds

    while True:
        try:
            response = requests.post(url, json=payload, timeout=60)
            response.raise_for_status()
            result = response.json()
            captcha_logger.info(f"2Captcha getTaskResult response: {result}")

            if result.get('status') == "ready":
                return result.get('solution')
            elif result.get('status') == "processing":
                logger.info(f"Captcha not ready yet. Waiting for {retry_delay} seconds before retrying...")
                time.sleep(retry_delay)
                retry_delay = min(retry_delay * 2, max_delay)  # Exponential backoff
                continue
            else:
                logger.error(f"Error from 2Captcha: {result.get('errorDescription')}")
                return None
        except requests.Timeout:
            logger.error("Request to 2Captcha timed out while fetching task result.")
            logger.info(f"Waiting for {retry_delay} seconds before retrying...")
            time.sleep(retry_delay)
            retry_delay = min(retry_delay * 2, max_delay)  # Exponential backoff
            continue
        except requests.ConnectionError:
            logger.error("Connection error occurred while fetching task result from 2Captcha.")
            logger.info(f"Waiting for {retry_delay} seconds before retrying...")
            time.sleep(retry_delay)
            retry_delay = min(retry_delay * 2, max_delay)
            continue
        except requests.HTTPError as e:
            logger.error(f"HTTP error occurred while fetching task result: {e}")
            return None
        except requests.RequestException as e:
            logger.error(f"An error occurred while fetching task result: {e}")
            logger.info(f"Waiting for {retry_delay} seconds before retrying...")
            time.sleep(retry_delay)
            retry_delay = min(retry_delay * 2, max_delay)
            continue

def handle_verify(driver):
    logger.info("'Verify' detected. Proceeding to verify the captcha.")
    # Click the Verify button
    click_coordinate(driver, *VERIFY_BUTTON)
    logger.info("Clicked the Verify button.")
    time.sleep(3)  # Wait for 3 seconds before starting continuous monitoring
    # Start continuous monitoring after clicking Verify
    handle_continuous_monitoring(driver)
    return True

def handle_try_again(driver):
    logger.info("'TRY AGAIN' detected. Clicking the Try Again button.")
    # Click the Try Again button
    click_coordinate(driver, *TRY_AGAIN_BUTTON)
    logger.info("Clicked the Try Again button.")
    time.sleep(3)  # Wait for the retry process to initiate

    # Before taking a screenshot, check for the accessibility ID
    if not ensure_captcha_present(driver):
        return False  # Captcha is not present, session is likely over

    # Take a new screenshot after clicking Try Again
    captcha_base64, instructions, screenshot_path = take_captcha_screenshot(driver)
    if not captcha_base64 or not instructions:
        logger.error("Failed to extract captcha information after clicking Try Again.")
        return False

    instructions_lower = instructions.lower()
    if "verify" in instructions_lower:
        logger.info("'Verify' detected after Try Again. Clicking the Verify button.")
        # Click the Verify button again
        click_coordinate(driver, *VERIFY_BUTTON)
        logger.info("Clicked the Verify button after Try Again.")
        time.sleep(3)  # Wait before starting continuous monitoring
        # Start continuous monitoring after clicking Verify
        handle_continuous_monitoring(driver)
    else:
        logger.info("'Verify' not detected after Try Again. Taking another screenshot.")
        # Take another screenshot and decide to click Verify
        captcha_base64, instructions, screenshot_path = take_captcha_screenshot(driver)
        if "verify" in instructions.lower():
            logger.info("'Verify' detected on second attempt. Clicking the Verify button.")
            click_coordinate(driver, *VERIFY_BUTTON)
            logger.info("Clicked the Verify button on second attempt.")
            time.sleep(3)  # Wait before starting continuous monitoring
            # Start continuous monitoring after clicking Verify
            handle_continuous_monitoring(driver)
        else:
            logger.info("'Verify' not detected on second attempt. Skipping Verify click.")

    return True

def handle_continuous_monitoring(driver):
    logger.info("Starting continuous monitoring for captcha parameters.")
    while True:
        time.sleep(3)  # Wait for 3 seconds before taking the next screenshot

        # Before taking a screenshot, check for the accessibility ID
        if not ensure_captcha_present(driver):
            return False  # Captcha is not present, session is likely over

        captcha_base64, instructions, screenshot_path = take_captcha_screenshot(driver)
        if not captcha_base64 or not instructions:
            logger.error("Failed to extract captcha information during continuous monitoring.")
            return False

        instructions_lower = instructions.lower()

        # Determine img_type based on instructions
        img_type = determine_img_type(instructions_lower)

        # Check if the necessary parameters are present (i.e., a comment)
        if any(keyword in instructions_lower for keyword in ["pick", "select", "match"]):
            logger.info("Required captcha parameters found. Preparing to send to 2Captcha.")
            # Send to 2Captcha
            task_id = send_to_2captcha("GridTask", img_type, captcha_base64, instructions)
            if not task_id:
                logger.error("Failed to create task on 2Captcha during continuous monitoring.")
                return False

            logger.info(f"Submitted task to 2Captcha. Task ID: {task_id}")

            # Get solution from 2Captcha
            solution = get_2captcha_result(task_id)
            if not solution:
                logger.error("Failed to get solution from 2Captcha during continuous monitoring.")
                return False

            logger.info(f"Received solution from 2Captcha: {solution}")

            if 'click' in solution:
                return apply_captcha_solution(driver, solution['click'])
            else:
                logger.error(f"Unexpected solution format during continuous monitoring: {solution}")
                return False

        elif "verification complete" in instructions_lower:
            logger.info("Verification Complete detected during continuous monitoring.")
            time.sleep(5)  # Wait for 5 seconds before checking for new captchas
            break  # Exit monitoring after successful verification

        else:
            logger.info("Captcha parameters not yet found. Continuing monitoring.")

    return True

def handle_multiple_captchas(driver, instructions_lower):
    logger.info("Checking for multiple captchas based on extracted instructions.")
    # If none of the keywords "verify", "try again", "verification complete" are present
    # but a comment is detected, assume another captcha is present
    if not any(keyword in instructions_lower for keyword in ["verify", "try again", "verification complete"]) and instructions_lower:
        logger.info("Detected a comment indicating another captcha is present.")

        # Before taking a screenshot, check for the accessibility ID
        if not ensure_captcha_present(driver):
            return False  # Captcha is not present, session is likely over

        # Take a screenshot to get the new captcha image
        captcha_base64, instructions, screenshot_path = take_captcha_screenshot(driver)
        if not captcha_base64 or not instructions:
            logger.error("Failed to extract captcha information for the new captcha.")
            return False

        # Determine img_type based on instructions
        img_type = determine_img_type(instructions_lower)

        # Send to 2Captcha
        task_id = send_to_2captcha("GridTask", img_type, captcha_base64, instructions)
        if not task_id:
            logger.error("Failed to create task on 2Captcha for the new captcha.")
            return False

        logger.info(f"Submitted new task to 2Captcha. Task ID: {task_id}")

        # Get solution from 2Captcha
        solution = get_2captcha_result(task_id)
        if not solution:
            logger.error("Failed to get solution from 2Captcha for the new captcha.")
            return False

        logger.info(f"Received solution from 2Captcha for the new captcha: {solution}")

        if 'click' in solution:
            return apply_captcha_solution(driver, solution['click'])
        else:
            logger.error("No 'click' solution found in the captcha solution for the new captcha.")
            return False

    logger.info("No multiple captchas detected based on instructions.")
    return True

def handle_verification_complete():
    logger.info("Verification Complete detected. Captcha solved successfully.")
    time.sleep(5)  # Wait for 5 seconds before checking for new captchas

def apply_captcha_solution(driver, clicks):
    try:
        logger.info(f"Need to click cells: {clicks}")
        for cell in clicks:
            if 1 <= cell <= len(CELLS):
                # Click the cell
                click_coordinate(driver, *CELLS[cell-1])
                logger.info(f"Clicked on cell {cell} at coordinates {CELLS[cell-1]}.")
                time.sleep(random.uniform(3, 5))  # Wait between 3 to 5 seconds after clicking a cell
            else:
                logger.error(f"Invalid cell number: {cell}")

        # Before taking a screenshot, check for the accessibility ID
        if not ensure_captcha_present(driver):
            return False  # Captcha is not present, session is likely over

        # After clicking cells, take a screenshot to decide next action
        captcha_base64, instructions, screenshot_path = take_captcha_screenshot(driver)
        if not captcha_base64 or not instructions:
            logger.error("Failed to extract captcha information after clicking cells.")
            return False

        instructions_lower = instructions.lower()

        # Click "Verify" only if "verify" is present in the text
        if "verify" in instructions_lower:
            logger.info("'Verify' detected in instructions. Clicking the Verify button.")
            click_coordinate(driver, *VERIFY_BUTTON)
            logger.info("Clicked the Verify button.")
            time.sleep(3)  # Wait before starting continuous monitoring
            # Start continuous monitoring after clicking Verify
            handle_continuous_monitoring(driver)
        else:
            logger.info("'Verify' not required based on instructions. Skipping Verify click.")

        # After handling "Verify", check for additional captchas
        logger.info("Checking for additional captchas after solving one captcha.")
        if not ensure_captcha_present(driver):
            return False  # Captcha is not present, session is likely over

        captcha_base64, instructions, screenshot_path = take_captcha_screenshot(driver)
        if not captcha_base64 or not instructions:
            logger.error("Failed to extract captcha information after solving a captcha.")
            return False

        instructions_lower = instructions.lower()

        if not any(keyword in instructions_lower for keyword in ["verify", "try again", "verification complete"]) and instructions_lower:
            logger.info("Detected a comment indicating another captcha is present.")
            return handle_multiple_captchas(driver, instructions_lower)

        elif "verification complete" in instructions_lower:
            handle_verification_complete()

        return True
    except Exception as e:
        logger.error(f"Error while applying captcha solution: {e}")
        return False

def ensure_captcha_present(driver):
    absence_count = 0
    max_absence_checks = 3
    while absence_count < max_absence_checks:
        if detect_captcha(driver):
            return True  # Captcha is present
        else:
            absence_count += 1
            logger.info(f"Captcha not detected. Absence count: {absence_count}")
            time.sleep(5)
    # If we reach here, captcha is not present after max_absence_checks
    logger.info("Captcha not detected after multiple checks. Deleting session directory.")
    delete_session_directory()
    return False

def solve_captcha(driver):
    max_attempts = 5  # Set the maximum number of attempts
    attempt = 0

    while attempt < max_attempts:
        attempt += 1
        logger.info(f"Captcha solving attempt {attempt} of {max_attempts}.")

        # Before taking a screenshot, check for the accessibility ID
        if not ensure_captcha_present(driver):
            return True  # Captcha is not present, session is likely over

        # Step 1: Take screenshot before any interaction
        captcha_base64, instructions, screenshot_path = take_captcha_screenshot(driver)
        if not captcha_base64 or not instructions:
            logger.error("Failed to extract captcha information before interaction.")
            return False

        # Step 2: Extract and search for keywords in instructions
        instructions_lower = instructions.lower()

        has_verify = "verify" in instructions_lower
        has_try_again = "try again" in instructions_lower
        has_verification_complete = "verification complete" in instructions_lower

        # Step 3: Define actions based on keyword presence
        if has_verification_complete:
            handle_verification_complete()
            # Start absence check
            if not ensure_captcha_present(driver):
                return True  # Captcha is not present, session is likely over
            continue  # Continue the loop to check for new captchas

        if has_try_again:
            if not handle_try_again(driver):
                return False
            continue  # Restart the loop after handling "TRY AGAIN"

        if has_verify:
            if not handle_verify(driver):
                return False
            continue  # Continue the loop to handle potential new captchas

        # If none of the keywords are present, check for multiple captchas
        if not handle_multiple_captchas(driver, instructions_lower):
            return False

        # Wait a short period before the next iteration
        time.sleep(3)

    logger.error("Maximum captcha solving attempts reached.")
    return False

def delete_session_directory():
    try:
        shutil.rmtree(SESSION_DIR)
        logger.info(f"Session directory {SESSION_DIR} deleted successfully.")
    except Exception as e:
        logger.error(f"Failed to delete session directory {SESSION_DIR}: {e}")

def main():
    driver = initialize_appium_driver()
    try:
        logger.info("Ready to start captcha verification process.")
        print("Press Enter when you're ready to start captcha verification...")
        input()

        while True:
            if detect_captcha(driver):
                logger.info("Captcha detected. Starting solving process.")
                success = solve_captcha(driver)
                if success:
                    logger.info("Captcha solving process completed successfully.")
                    # Session directory deletion is handled within the functions
                    break
                else:
                    logger.info("Retrying captcha solving process.")
            else:
                logger.info("No captcha detected. Checking again in 5 seconds.")
                time.sleep(5)
    except KeyboardInterrupt:
        logger.info("Script terminated by user.")
    finally:
        driver.quit()
        logger.info("Appium driver session ended.")

if __name__ == "__main__":
    main()
