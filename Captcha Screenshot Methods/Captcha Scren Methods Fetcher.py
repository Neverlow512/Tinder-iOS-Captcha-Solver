import os
import time
import json
from appium import webdriver
from appium.webdriver.common.appiumby import AppiumBy
import logging
import sys

# ===========================
# Configuration and Setup
# ===========================

# Appium Server Configuration
APPUM_SERVER_URL = "http://localhost:4723/wd/hub"

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
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler("logs/step1_script.log"),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# XPath for Captcha Element
CAPTCHA_XPATH = '//XCUIElementTypeApplication[@name="Tinder"]/XCUIElementTypeWindow[1]/XCUIElementTypeOther[3]/XCUIElementTypeOther/XCUIElementTypeOther[2]/XCUIElementTypeWebView/XCUIElementTypeWebView/XCUIElementTypeWebView/XCUIElementTypeOther/XCUIElementTypeOther/XCUIElementTypeOther/XCUIElementTypeOther'

# ===========================
# Helper Functions
# ===========================

def initialize_appium_driver():
    try:
        driver = webdriver.Remote(APPUM_SERVER_URL, desired_caps)
        logger.info("Connected to Appium server successfully.")
        logger.info(f"Session ID: {driver.session_id}")
        time.sleep(5)  # Wait for the app to stabilize
        return driver
    except Exception as e:
        logger.error(f"Failed to connect to Appium server: {e}")
        sys.exit(1)

def locate_captcha_element(driver):
    try:
        captcha_element = driver.find_element(AppiumBy.XPATH, CAPTCHA_XPATH)
        logger.info("Captcha element located successfully.")
        return captcha_element
    except Exception as e:
        logger.error(f"Failed to locate captcha element using XPath: {e}")
        return None

def get_element_info(element):
    location = element.location
    size = element.size
    logger.info(f"Element Location: {location}")
    logger.info(f"Element Size: {size}")
    return location, size

def get_screen_size(driver):
    size = driver.get_window_size()
    logger.info(f"Screen Size: {size}")
    return size

def calculate_coordinates(location, size, screen_size):
    # Absolute Coordinates (Top-Left Corner)
    absolute_coords = {
        "x": location['x'],
        "y": location['y'],
        "width": size['width'],
        "height": size['height']
    }

    # Relative Coordinates (Proportion of Screen Size)
    relative_coords = {
        "x_ratio": location['x'] / screen_size['width'],
        "y_ratio": location['y'] / screen_size['height'],
        "width_ratio": size['width'] / screen_size['width'],
        "height_ratio": size['height'] / screen_size['height']
    }

    # Percentage-Based Coordinates (Center Point)
    center_x = location['x'] + size['width'] / 2
    center_y = location['y'] + size['height'] / 2
    percentage_coords = {
        "center_x_pct": center_x / screen_size['width'],
        "center_y_pct": center_y / screen_size['height']
    }

    logger.info(f"Absolute Coordinates: {absolute_coords}")
    logger.info(f"Relative Coordinates: {relative_coords}")
    logger.info(f"Percentage-Based Coordinates: {percentage_coords}")

    return absolute_coords, relative_coords, percentage_coords

def store_coordinates(method_name, data):
    os.makedirs("stored_coordinates", exist_ok=True)
    filename = f"stored_coordinates/{method_name}_coordinates.json"
    try:
        with open(filename, 'w') as f:
            json.dump(data, f, indent=2)
        logger.info(f"Stored {method_name} coordinates in {filename}")
    except Exception as e:
        logger.error(f"Failed to store {method_name} coordinates: {e}")

# ===========================
# Main Execution
# ===========================

def main():
    driver = initialize_appium_driver()
    try:
        captcha_element = locate_captcha_element(driver)
        if not captcha_element:
            logger.error("Captcha element not found. Exiting script.")
            return

        location, size = get_element_info(captcha_element)
        screen_size = get_screen_size(driver)
        absolute_coords, relative_coords, percentage_coords = calculate_coordinates(location, size, screen_size)

        # Store each method's coordinates in separate files
        store_coordinates("absolute", absolute_coords)
        store_coordinates("relative", relative_coords)
        store_coordinates("percentage", percentage_coords)

        # Optionally, capture a screenshot of the captcha element
        screenshot_filename = f"screenshots/captcha_element_{int(time.time())}.png"
        os.makedirs("screenshots", exist_ok=True)
        try:
            captcha_element.screenshot(screenshot_filename)
            logger.info(f"Screenshot of captcha element saved as {screenshot_filename}")
        except Exception as e:
            logger.error(f"Failed to take screenshot of captcha element: {e}")

    finally:
        driver.quit()
        logger.info("Appium driver session ended.")

if __name__ == "__main__":
    main()
