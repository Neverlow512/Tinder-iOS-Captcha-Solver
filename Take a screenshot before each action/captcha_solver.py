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

# Appium Driver Configuration
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
        captcha_element = driver.find_element(AppiumBy.XPATH, '//XCUIElementTypeTextView')
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
    screenshot_base64 = captcha_element.screenshot_as_base64
    image_data = base64.b64decode(screenshot_base64)
    captcha_image = Image.open(io.BytesIO(image_data))

    # Save the screenshot
    timestamp = time.strftime("%Y%m%d-%H%M%S")
    screenshot_filename = f"screenshots/captcha_screenshot_{timestamp}.png"
    captcha_image.save(screenshot_filename)
    logger.info(f"Saved captcha screenshot to {screenshot_filename}")

    # Extract instructions using OCR
    instructions = pytesseract.image_to_string(captcha_image).strip()
    logger.info(f"Extracted instructions from screenshot: '{instructions}'")

    return screenshot_base64, instructions, screenshot_filename

def send_to_2captcha(task_type, img_type, captcha_base64, instructions):
    url = "https://api.2captcha.com/createTask"

    payload = {
        "clientKey": API_KEY,
        "task": {
            "type": "GridTask",
            "body": captcha_base64,
            "comment": instructions,
            "imgType": img_type
        }
    }

    try:
        response = requests.post(url, json=payload, timeout=30)
        response.raise_for_status()
        data = response.json()
        captcha_logger.info(f"2Captcha createTask response: {response.text}")

        if 'taskId' in data:
            return data['taskId']
        else:
            logger.error(f"Unexpected response structure: {data}")
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

    while True:
        try:
            response = requests.post(url, json=payload, timeout=30)
            response.raise_for_status()
            result = response.json()
            captcha_logger.info(f"2Captcha getTaskResult response: {result}")

            if result.get('status') == "ready":
                return result.get('solution')
            elif result.get('status') == "processing":
                logger.info("Captcha not ready yet. Waiting for 5 seconds before retrying...")
                time.sleep(5)
                continue
            else:
                logger.error(f"Error from 2Captcha: {result.get('errorDescription')}")
                return None
        except requests.RequestException as e:
            logger.error(f"Error fetching task result: {e}")
            time.sleep(5)

def verify_captcha_status(driver):
    captcha_element = find_captcha_element(driver)
    if not captcha_element:
        return "error"

    screenshot_base64 = captcha_element.screenshot_as_base64
    image_data = base64.b64decode(screenshot_base64)
    captcha_image = Image.open(io.BytesIO(image_data))

    # Process image for better OCR accuracy
    captcha_image = captcha_image.convert('L')
    captcha_image = captcha_image.point(lambda x: 0 if x < 140 else 255, '1')

    status_text = pytesseract.image_to_string(captcha_image).strip().lower()
    logger.info(f"Captcha Status Text: '{status_text}'")

    if "verification complete" in status_text:
        return "success"
    elif "try again" in status_text or "error" in status_text:
        return "retry"
    elif any(keyword in status_text for keyword in ["cell", "select", "pick"]):
        return "continue"
    else:
        return "continue"

# def check_for_buttons(driver):
#     try:
#         verify_button = driver.find_element(AppiumBy.ACCESSIBILITY_ID, "Verify")
#         return "verify"
#     except:
#         try:
#             try_again_button = driver.find_element(AppiumBy.ACCESSIBILITY_ID, "Try Again")
#             return "try_again"
#         except:
#             return None

def solve_captcha(driver):
    while True:
        # Step 2.1: Take screenshot before clicking Verify
        captcha_base64, instructions, screenshot_path = take_captcha_screenshot(driver)
        if not captcha_base64 or not instructions:
            logger.error("Failed to extract captcha information before clicking Verify.")
            return False

        # Click the Verify button
        click_coordinate(driver, *VERIFY_BUTTON)
        logger.info("Clicked the Verify button.")
        time.sleep(2)

        # Step 2.2: Take screenshot before sending to 2Captcha
        captcha_base64, instructions, screenshot_path = take_captcha_screenshot(driver)
        if not captcha_base64 or not instructions:
            logger.error("Failed to extract captcha information before sending to 2Captcha.")
            return False

        # Determine imgType based on instructions
        img_type = "funcaptcha" if any(keyword in instructions.lower() for keyword in ["pick", "select"]) else "funcaptcha_compare"
        logger.info(f"Determined imgType: {img_type}")

        # Send to 2Captcha
        task_id = send_to_2captcha("GridTask", img_type, captcha_base64, instructions)
        if not task_id:
            logger.error("Failed to create task on 2Captcha.")
            return False

        logger.info(f"Submitted task to 2Captcha. Task ID: {task_id}")

        # Get solution from 2Captcha
        solution = get_2captcha_result(task_id)
        if not solution:
            logger.error("Failed to get solution from 2Captcha.")
            return False

        logger.info(f"Received solution from 2Captcha: {solution}")

        if 'click' in solution:
            try:
                clicks = solution['click']
                logger.info(f"Need to click cells: {clicks}")
                for cell in clicks:
                    if 1 <= cell <= len(CELLS):
                        # Step 2.3: Take screenshot before clicking each cell
                        captcha_base64, instructions, screenshot_path = take_captcha_screenshot(driver)
                        if not captcha_base64 or not instructions:
                            logger.error(f"Failed to extract captcha information before clicking cell {cell}.")
                            return False

                        click_coordinate(driver, *CELLS[cell-1])
                        logger.info(f"Clicked on cell {cell} at coordinates {CELLS[cell-1]}.")
                        time.sleep(random.uniform(0.5, 1.5))
                    else:
                        logger.error(f"Invalid cell number: {cell}")

                # Step 2.4: Take screenshot before clicking Verify after selecting cells
                captcha_base64, instructions, screenshot_path = take_captcha_screenshot(driver)
                if not captcha_base64 or not instructions:
                    logger.error("Failed to extract captcha information before clicking Verify after selecting cells.")
                    return False

                # Click Verify after selecting cells
                click_coordinate(driver, *VERIFY_BUTTON)
                logger.info("Clicked the Verify button after selecting cells.")
                time.sleep(3)

                # Check captcha status
                status = verify_captcha_status(driver)
                if status == "success":
                    logger.info("Captcha solved successfully!")
                    return True
                elif status == "retry":
                    logger.info("Captcha failed. Clicking 'Try Again' and retrying.")
                    
                    # Step 2.5: Take screenshot before clicking Try Again
                    captcha_base64, instructions, screenshot_path = take_captcha_screenshot(driver)
                    if not captcha_base64 or not instructions:
                        logger.error("Failed to extract captcha information before clicking Try Again.")
                        return False

                    click_coordinate(driver, *TRY_AGAIN_BUTTON)
                    logger.info("Clicked the Try Again button.")
                    time.sleep(2)
                    continue
                else:
                    logger.info("Captcha requires further solving. Continuing...")
            except Exception as e:
                logger.error(f"Error while solving captcha: {e}")
                return False
        else:
            logger.error(f"Unexpected solution format: {solution}")
            return False


def main():
    driver = initialize_appium_driver()
    try:
        logger.info("Ready to start captcha verification process.")
        input("Press Enter when you're ready to start captcha verification...")

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