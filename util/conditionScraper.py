import time
import json
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

def scroll_and_click(driver, wait, selector, by=By.CSS_SELECTOR, description="element"):
    try:
        elem = wait.until(EC.element_to_be_clickable((by, selector)))
        driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", elem)
        driver.execute_script("arguments[0].click();", elem)
        print(f"Clicked {description}.")
        return True
    except Exception as e:
        print(f"Could not click {description}: {e}")
        return False

# Setup
path = "C:\\Users\\kevin\\Downloads\\chromedriver-win64\\chromedriver-win64\\chromedriver.exe"
URL = "https://gametora.com/umamusume/skill-condition-viewer"

service = Service(executable_path=path)
driver = webdriver.Chrome(service=service)
driver.get(URL)
wait = WebDriverWait(driver, 10)
output = {}

# Get all conditions (excluding hidden)
containers = driver.find_elements(By.CSS_SELECTOR, ".conditionviewer_cond__LnQzc")
print(f"Found {len(containers)} visible skill containers")

for container in containers:
    try:
        name = container.find_element(By.CLASS_NAME, "conditionviewer_cond_name__WOrIu").text.strip()

        print(f"\n--- Scraping: {name} ---")

        divs = container.find_elements(By.TAG_NAME, "div")
        description = divs[1].text.strip() if len(divs) > 1 else ""
        example = ""
        meaning = ""

        for div in divs[2:]:
            text = div.text.strip()
            if text.startswith("Example:"):
                example = text.replace("Example:", "").strip()
            elif text.startswith("Meaning:"):
                meaning = text.replace("Meaning:", "").strip()

        output[name] = {
            "description": description,
            "example": example,
            "meaning": meaning
        }

    except Exception as e:
        print(f"Error scraping container: {e}")

# Save JSON
with open("conditions.json", "w", encoding="utf-8") as f:
    json.dump(output, f, indent=2, ensure_ascii=False)

print("\nSaved to conditions.json")
driver.quit()
