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

# ===========================
# Configuration and Setup
# ===========================

API_KEY = "f6bec1a088dce763cab65ee11154e2cb"  # Replace with your actual 2Captcha API key

if not API_KEY or API_KEY == "YOUR_2CAPTCHA_API_KEY":
    print("Error: Please replace 'YOUR_2CAPTCHA_API_KEY' with your actual 2Captcha API key.")
    sys.exit(1)

# Logging Configuration
os.makedirs("logs", exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler("logs/general.log"),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

captcha_logger = logging.getLogger('2captcha')
captcha_logger.setLevel(logging.INFO)
captcha_handler = logging.FileHandler('logs/2captcha_interactions.log')
captcha_handler.setLevel(logging.INFO)
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
    "useNewWDA": True,
    "noReset": True
}

appium_server_url = "http://localhost:4723/wd/hub"

# Screenshots Directory Configuration
os.makedirs("screenshots", exist_ok=True)

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

def initialize_appium_driver():
    while True:
        try:
            driver = webdriver.Remote(appium_server_url, desired_caps)
            logger.info("Appium server started and connected successfully.")
            logger.info(f"Session ID: {driver.session_id}")
            return driver
        except Exception as e:
            logger.error(f"Failed to connect to Appium server: {e}")
            logger.info("Retrying in 2 seconds...")
            time.sleep(2)

os.makedirs("2captcha_payloads", exist_ok=True)

def log_2captcha_payload(payload):
    timestamp = time.strftime("%Y%m%d-%H%M%S")
    filename = f"2captcha_payloads/payload_{timestamp}.json"
    with open(filename, 'w') as f:
        json.dump(payload, f, indent=2)
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

def find_captcha_element(driver):
    try:
        captcha_element = driver.find_element(AppiumBy.XPATH, '//XCUIElementTypeApplication[@name="Tinder"]/XCUIElementTypeWindow[1]/XCUIElementTypeOther[3]/XCUIElementTypeOther/XCUIElementTypeOther[2]/XCUIElementTypeOther/XCUIElementTypeWebView/XCUIElementTypeTextView')
        return captcha_element
    except Exception as e:
        logger.error(f"Failed to find captcha element: {e}")
        return None

def take_captcha_screenshot(driver):
    captcha_element = find_captcha_element(driver)
    if not captcha_element:
        logger.error("Captcha element not found.")
        return None, None, None

    # Capture screenshot of the specific element
    try:
        screenshot_base64 = captcha_element.screenshot_as_base64
    except Exception as e:
        logger.error(f"Failed to capture screenshot as base64: {e}")
        return None, None, None

    if not screenshot_base64:
        logger.error("Screenshot base64 is empty.")
        return None, None, None

    image_data = base64.b64decode(screenshot_base64)
    try:
        captcha_image = Image.open(io.BytesIO(image_data))
    except Exception as e:
        logger.error(f"Failed to open image from screenshot: {e}")
        return None, None, None

    # Save the screenshot
    timestamp = time.strftime("%Y%m%d-%H%M%S")
    screenshot_filename = f"screenshots/captcha_screenshot_{timestamp}.png"
    try:
        captcha_image.save(screenshot_filename)
        logger.info(f"Saved captcha screenshot to {screenshot_filename}")
    except Exception as e:
        logger.error(f"Failed to save captcha screenshot: {e}")
        return None, None, None

    # Extract instructions using OCR
    try:
        instructions = pytesseract.image_to_string(captcha_image).strip()
        logger.info(f"Extracted instructions from screenshot: '{instructions}'")
    except Exception as e:
        logger.error(f"Failed to perform OCR on captcha image: {e}")
        instructions = ""

    return screenshot_base64, instructions, screenshot_filename

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

def verify_captcha_status(driver):
    captcha_element = find_captcha_element(driver)
    if not captcha_element:
        return "error"

    try:
        screenshot_base64 = captcha_element.screenshot_as_base64
    except Exception as e:
        logger.error(f"Failed to capture screenshot as base64 for status verification: {e}")
        return "error"

    if not screenshot_base64:
        logger.error("Screenshot base64 is empty for status verification.")
        return "error"

    try:
        image_data = base64.b64decode(screenshot_base64)
        captcha_image = Image.open(io.BytesIO(image_data))
    except Exception as e:
        logger.error(f"Failed to open image from screenshot for status verification: {e}")
        return "error"

    # Extract text using OCR without modifying the image
    try:
        status_text = pytesseract.image_to_string(captcha_image).strip().lower()
        logger.info(f"Captcha Status Text: '{status_text}'")
    except Exception as e:
        logger.error(f"Failed to perform OCR on captcha image for status verification: {e}")
        status_text = ""

    if "verification complete" in status_text:
        return "success"
    elif "try again" in status_text or "error" in status_text:
        return "retry"
    elif any(keyword in status_text for keyword in ["cell", "select", "pick"]):
        return "continue"
    else:
        return "continue"

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

def solve_captcha(driver):
    max_attempts = 5  # Set the maximum number of attempts
    attempt = 0

    while attempt < max_attempts:
        attempt += 1
        logger.info(f"Captcha solving attempt {attempt} of {max_attempts}.")

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
