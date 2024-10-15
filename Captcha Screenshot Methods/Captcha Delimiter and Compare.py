import os
import time
import json
from appium import webdriver
from appium.webdriver.common.appiumby import AppiumBy
import cv2
import numpy as np
import logging
import sys
from PIL import Image
import io
import base64

# ===========================
# Configuration and Setup
# ===========================

# Appium Server Configuration
APPIUM_SERVER_URL = "http://localhost:4723/wd/hub"

# Desired Capabilities (as provided)
desired_caps = {
    "xcodeOrgId": "9VG3A52D8L",
    "xcodeSigningId": "iPhone Developer",
    "platformName": "iOS",
    "automationName": "XCUITest",
    "udid": "00008030-001235042107802E",
    "deviceName": "iPhone",
    "bundleId": "com.cardify.tinder",
    "updatedWDABundleID": "NumbLegacy.TinderLegacyNumb.WebDriverAgentRunner",
    "showXcodeLog": True,
    "newCommandTimeout": 300,
    "usePrebuiltWDA": True,
    "useNewWDA": True,
    "noReset": True
}

# Logging Configuration
os.makedirs("logs", exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("logs/image_matching_script.log"),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# XPath for Captcha Element (used to get the reference image)
CAPTCHA_XPATH = '//XCUIElementTypeApplication[@name="Tinder"]/XCUIElementTypeWindow[1]/XCUIElementTypeOther[3]/XCUIElementTypeOther/XCUIElementTypeOther[2]/XCUIElementTypeOther/XCUIElementTypeWebView/XCUIElementTypeTextView'

# Output Directories
os.makedirs("screenshots", exist_ok=True)
os.makedirs("stored_coordinates", exist_ok=True)

# ===========================
# Helper Functions
# ===========================

def initialize_appium_driver():
    try:
        driver = webdriver.Remote(APPIUM_SERVER_URL, desired_caps)
        logger.info("Connected to Appium server successfully.")
        logger.info(f"Session ID: {driver.session_id}")
        time.sleep(5)  # Wait for the app to stabilize
        return driver
    except Exception as e:
        logger.error(f"Failed to connect to Appium server: {e}")
        sys.exit(1)

def capture_reference_image(driver):
    try:
        captcha_element = driver.find_element(AppiumBy.XPATH, CAPTCHA_XPATH)
        logger.info("Captcha element located successfully for reference image.")

        # Capture screenshot of the captcha element
        timestamp = int(time.time())
        reference_image_path = f"screenshots/captcha_reference_{timestamp}.png"
        captcha_element.screenshot(reference_image_path)
        logger.info(f"Reference image saved as {reference_image_path}")
        return reference_image_path
    except Exception as e:
        logger.error(f"Failed to capture reference image: {e}")
        return None

def capture_full_screen_image(driver):
    try:
        screenshot_base64 = driver.get_screenshot_as_base64()
        image_data = base64.b64decode(screenshot_base64)
        full_screen_image = Image.open(io.BytesIO(image_data))
        timestamp = int(time.time())
        full_screen_image_path = f"screenshots/full_screen_{timestamp}.png"
        full_screen_image.save(full_screen_image_path)
        logger.info(f"Full-screen image saved as {full_screen_image_path}")
        return full_screen_image_path
    except Exception as e:
        logger.error(f"Failed to capture full-screen image: {e}")
        return None

def perform_image_matching(full_screen_image_path, reference_image_path):
    try:
        # Load images using OpenCV
        full_image = cv2.imread(full_screen_image_path)
        ref_image = cv2.imread(reference_image_path)

        if full_image is None or ref_image is None:
            logger.error("Failed to read images using OpenCV.")
            return None

        # Convert images to grayscale
        full_gray = cv2.cvtColor(full_image, cv2.COLOR_BGR2GRAY)
        ref_gray = cv2.cvtColor(ref_image, cv2.COLOR_BGR2GRAY)

        # Template matching
        result = cv2.matchTemplate(full_gray, ref_gray, cv2.TM_CCOEFF_NORMED)
        min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)

        logger.info(f"Template matching max_val: {max_val}")

        # Define a threshold for matching
        threshold = 0.8  # Adjust this value as needed

        if max_val >= threshold:
            # Match found
            top_left = max_loc
            h, w = ref_gray.shape
            bottom_right = (top_left[0] + w, top_left[1] + h)

            # Draw rectangle on the full image (optional for verification)
            cv2.rectangle(full_image, top_left, bottom_right, (0, 255, 0), 2)
            matched_image_path = f"screenshots/matched_image_{int(time.time())}.png"
            cv2.imwrite(matched_image_path, full_image)
            logger.info(f"Matched area highlighted in image saved as {matched_image_path}")

            # Coordinates of the captcha area
            coordinates = {
                "x": top_left[0],
                "y": top_left[1],
                "width": w,
                "height": h
            }
            logger.info(f"Captcha area coordinates: {coordinates}")
            return coordinates
        else:
            logger.warning("Captcha area not found in full-screen image.")
            return None
    except Exception as e:
        logger.error(f"Error during image matching: {e}")
        return None

def store_coordinates(data):
    filename = f"stored_coordinates/image_matching_coordinates.json"
    try:
        with open(filename, 'w') as f:
            json.dump(data, f, indent=2)
        logger.info(f"Stored coordinates in {filename}")
    except Exception as e:
        logger.error(f"Failed to store coordinates: {e}")

# ===========================
# Main Execution
# ===========================

def main():
    driver = initialize_appium_driver()
    try:
        # Step 1: Capture Reference Image of Captcha
        reference_image_path = capture_reference_image(driver)
        if not reference_image_path:
            logger.error("Failed to capture reference image. Exiting script.")
            return

        # Step 2: Capture Full-Screen Screenshot
        full_screen_image_path = capture_full_screen_image(driver)
        if not full_screen_image_path:
            logger.error("Failed to capture full-screen image. Exiting script.")
            return

        # Step 3: Perform Image Matching to Locate Captcha Area
        coordinates = perform_image_matching(full_screen_image_path, reference_image_path)
        if not coordinates:
            logger.error("Failed to locate captcha area using image matching.")
            return

        # Step 4: Store the Coordinates
        store_coordinates(coordinates)

    finally:
        driver.quit()
        logger.info("Appium driver session ended.")

if __name__ == "__main__":
    main()
