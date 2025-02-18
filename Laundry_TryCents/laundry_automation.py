import os
import sys
import time
import shutil
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, ElementClickInterceptedException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.action_chains import ActionChains  # noqa

def setup_driver():
    try:
        print("Starting automation...")
        options = Options()

        # Set up paths
        chrome_profile = os.path.expanduser('~') + r'\AppData\Local\Google\Chrome\User Data'
        temp_profile = os.path.expanduser('~') + r'\AppData\Local\Temp\selenium_chrome_profile'

        # Clean up any existing temporary profile
        if os.path.exists(temp_profile):
            try:
                shutil.rmtree(temp_profile)
            except Exception as e:
                print(f"Error cleaning up temp profile: {e}")

        # Create temp directory and copy profile
        os.makedirs(temp_profile, exist_ok=True)
        try:
            # Copy Default folder and Local State
            shutil.copytree(os.path.join(chrome_profile, 'Default'),
                          os.path.join(temp_profile, 'Default'))
            shutil.copy2(os.path.join(chrome_profile, 'Local State'),
                        os.path.join(temp_profile, 'Local State'))
        except Exception as e:
            print(f"Error copying profile: {e}")

        # Set up Chrome options
        options.add_argument(f'--user-data-dir={temp_profile}')
        options.add_argument('--profile-directory=Default')
        options.add_argument('--new-window')

        # Disable automation flags
        options.add_experimental_option('excludeSwitches', ['enable-automation'])
        options.add_experimental_option('useAutomationExtension', False)
        options.add_argument('--disable-blink-features=AutomationControlled')

        print("Opening Chrome browser with temporary profile...")
        driver = webdriver.Chrome(options=options)
        driver.maximize_window()
        return driver
    except Exception as e:
        print(f"Error setting up driver: {e}")
        raise e

def click_element(driver, element, wait_time=3):
    try:
        # Wait for element to be present
        element_obj = WebDriverWait(driver, wait_time).until(
            EC.presence_of_element_located(element)
        )

        # Wait for element to be visible
        element_obj = WebDriverWait(driver, wait_time).until(
            EC.visibility_of_element_located(element)
        )

        # Scroll element into view
        driver.execute_script("arguments[0].scrollIntoView(true);", element_obj)
        time.sleep(1)  # Wait for scroll to complete

        # Try multiple click methods
        try:
            # Try regular click
            element_obj.click()
        except:
            try:
                # Try JavaScript click
                driver.execute_script("arguments[0].click();", element_obj)
            except:
                # Try moving to element then click
                actions = webdriver.ActionChains(driver)
                actions.move_to_element(element_obj).click().perform()

        return True
    except Exception as e:
        print(f"Error clicking element: {e}")
        return False

def main():
    driver = None
    try:
        driver = setup_driver()
        print("Driver setup complete")

        # Navigate to TryCents
        print("Navigating to TryCents...")
        driver.get("https://app.trycents.com/order/business/39/home")

        # Wait for page to fully load
        print("Waiting for page to load...")
        WebDriverWait(driver, 20).until(
            EC.presence_of_element_located((By.TAG_NAME, "body"))
        )

        # Check if we need to log in
        try:
            login_button = WebDriverWait(driver, 5).until(
                EC.presence_of_element_located((By.XPATH, "//button[contains(text(), 'Login')]"))
            )
            print("Login required. Please log in manually...")
            input("Press Enter after logging in...")
        except TimeoutException:
            print("Already logged in")

        print("Page loaded")
        time.sleep(5)  # Additional wait for page to stabilize

        # Try different selectors for New Order button
        print("Looking for New Order button...")
        new_order_selectors = [
            (By.XPATH, '//*[@id="root"]/div/div[1]/div[2]/div[1]/div/div[4]/button'),
            (By.XPATH, "//button[contains(text(), 'New Order')]"),
            (By.XPATH, "//button[text()='New Order']"),
            (By.CSS_SELECTOR, "button.MuiButton-root:contains('New Order')")
        ]

        clicked = False
        for selector in new_order_selectors:
            if click_element(driver, selector, wait_time=10):
                clicked = True
                break

        if not clicked:
            raise Exception("Failed to click New Order")

        print("Clicked New Order button")
        time.sleep(3)  # Wait for next page

        # Click Wash and Fold section
        print("Looking for Wash and Fold section...")
        wash_fold_section = (By.XPATH, '//*[@id="root"]/div/div[1]/div[2]/div[1]/main/section/div[3]/div[3]/div/div[3]/button')
        if not click_element(driver, wash_fold_section, wait_time=5):
            raise Exception("Failed to click Wash and Fold")
        print("Clicked Wash and Fold section")
        time.sleep(3)  # Wait for next section

        # Click Gain Detergent option
        print("Looking for Gain Detergent option...")
        gain_detergent = (By.XPATH, "/html/body/div[8]/div[3]/div/div[2]/div[3]/div[3]/div/p")
        if not click_element(driver, gain_detergent, wait_time=5):
            raise Exception("Failed to click Gain Detergent")
        print("Clicked Gain Detergent option")
        time.sleep(3)  # Wait before Save

        # Click Save button
        print("Looking for Save button...")
        save_button = (By.XPATH, "//button[text()='Save']")
        if not click_element(driver, save_button):
            raise Exception("Failed to click Save")
        print("Clicked Save button")
        time.sleep(3)  # Wait for next section

        # Click Next button
        print("Looking for Next button...")
        next_button = (By.XPATH, '//*[@id="root"]/div/div[1]/div[2]/div[1]/footer/button')
        if not click_element(driver, next_button, wait_time=5):
            raise Exception("Failed to click Next")
        print("Clicked Next button")
        time.sleep(3)  # Wait for next section

        # Click pencil icon first
        print("Looking for pencil icon...")
        pencil_icon = (By.XPATH, '//*[@id="schedule-form"]/div[1]/div[2]/span[1]')
        if not click_element(driver, pencil_icon, wait_time=5):
            raise Exception("Failed to click pencil icon")
        print("Clicked pencil icon")
        print("Waiting 15 seconds for time slot options to appear...")
        time.sleep(15)  # Extended wait for time slot options to appear

        # Select time slot
        print("Looking for time slot...")
        time_slot = (By.XPATH, "//h6[contains(text(), '04:30PM-06:00PM')]")
        if not click_element(driver, time_slot, wait_time=5):
            raise Exception("Failed to click time slot")
        print("Selected time slot")
        time.sleep(3)  # Wait for time slot to be selected

        # Click Set Pickup Time button
        print("Looking for Set Pickup Time button...")
        set_pickup_button = (By.XPATH, '//*[@id="root"]/div/div[1]/div[2]/main/section/aside/button')
        if not click_element(driver, set_pickup_button, wait_time=5):
            raise Exception("Failed to click Set Pickup Time")
        print("Clicked Set Pickup Time button")
        time.sleep(3)  # Wait for next section

        # Click final Next button
        print("Looking for final Next button...")
        final_next_button = (By.XPATH, '//*[@id="root"]/div/div[1]/div[2]/main/section/aside/button')
        if not click_element(driver, final_next_button, wait_time=5):
            raise Exception("Failed to click final Next button")
        print("Clicked final Next button")

        print("Automation completed successfully!")
        print("Waiting 25 seconds before closing...")
        time.sleep(25)  # Final wait before closing

    except Exception as e:
        print(f"Error during automation: {str(e)}")
    except KeyboardInterrupt:
        print("\nScript interrupted by user")
    finally:
        if driver:
            print("\nClosing browser...")
            try:
                driver.quit()
            except:
                pass
            print("Browser closed. Exiting program.")
            sys.exit(0)

if __name__ == "__main__":
    try:
        print("Starting script...")
        main()
    except Exception as e:
        print(f"Unexpected error: {str(e)}")
        sys.exit(1)