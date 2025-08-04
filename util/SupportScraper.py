import time
import json
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

def scroll_and_click(driver, wait, selector, by=By.CSS_SELECTOR, description="element"):
    try:
        elem = wait.until(EC.presence_of_element_located((by, selector)))
        driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", elem)
        wait.until(EC.element_to_be_clickable((by, selector)))
        elem.click()
        print(f"Clicked {description}.")
        return True
    except Exception as e:
        print(f"Could not click {description}: {e}")
        return False

def wait_and_click(driver, wait, selector, by=By.CSS_SELECTOR, description="element"):
    try:
        elem = wait.until(EC.element_to_be_clickable((by, selector)))
        elem.click()
        print(f"Clicked {description}.")
        return True
    except Exception as e:
        print(f"Could not click {description}: {e}")
        return False

path = "C:\\Users\\kevin\\Downloads\\chromedriver-win64\\chromedriver-win64\\chromedriver.exe"
URL = "https://gametora.com/umamusume/training-event-helper"

service = Service(executable_path=path)
driver = webdriver.Chrome(service=service)
driver.get(URL)

wait = WebDriverWait(driver, 10)

# Change scenario to URA Finals
wait_and_click(driver, wait, "//div[@class='compatibility_box_caption__IT3km' and text()='Career']", By.XPATH, "'Career' box")
wait_and_click(driver, wait, "//div[@class='sc-9ae1b094-1 hwTozI']/span[text()='URA Finals']", By.XPATH, "'URA Finals' option")

# Open settings and set filters
scroll_and_click(driver, wait, ".filters_settings_button_text__AfzDX", By.CSS_SELECTOR, "Settings button")
time.sleep(0.5)
wait_and_click(driver, wait, 'label[for="allAtOnceCheckbox"]', By.CSS_SELECTOR, "'Show all cards at once' label")
time.sleep(0.5)
wait_and_click(driver, wait, "#expandEventsCheckbox", By.CSS_SELECTOR, "'Expand Events' checkbox")
time.sleep(0.5)
wait_and_click(driver, wait, "#onlyChoicesCheckbox", By.CSS_SELECTOR, "'Only Choices' checkbox")
time.sleep(0.5)
wait_and_click(driver, wait, ".filters_confirm_button__6itTZ", By.CSS_SELECTOR, "'Confirm' button")
time.sleep(1)

# Open support character select box
wait_and_click(driver, wait, "boxSupport1", By.ID, "Support select box")
time.sleep(1)
checkbox = driver.find_element(By.ID, "checkboxShowR")
if not checkbox.is_selected():
    driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", checkbox)
    checkbox.click()
time.sleep(1)


# Find all support containers
supports = []
containers = driver.find_elements(By.CSS_SELECTOR, "div.sc-d7f35a8d-1.ifktje")
for c in containers:
    try:
        support_id = c.get_attribute("id")
        if support_id:
            supports.append((support_id, c))
    except Exception:
        continue

print(f"Found {len(supports)} support cards (including 'Remove'). Skipping the first.")

unique_events = {}

def add_events(scraped_events):
    for event_name, event_data in scraped_events.items():
        if event_name not in unique_events:
            unique_events[event_name] = event_data

for support_id, container in supports[0:]:  # Skip "Remove"
    print(f"\n--- Scraping Support ID: {support_id} ---")
    
    # Re-open support select box before clicking next
    wait_and_click(driver, wait, "boxSupport1", By.ID, "Support select box")
    time.sleep(1)
    
    # Re-find container
    containers = driver.find_elements(By.CSS_SELECTOR, "div.sc-d7f35a8d-1.ifktje")
    container = None
    for c in containers:
        try:
            if c.get_attribute("id") == support_id:
                container = c
                break
        except Exception:
            pass
    
    if container is None:
        print(f"Could not find container for Support ID: {support_id}")
        continue

    driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", container)
    
    try:
        driver.execute_script("arguments[0].click();", container)
    except Exception as e:
        print(f"JS click failed for Support ID {support_id}: {e}")
        container.click()
    
    time.sleep(1)
    
    # Scrape events
    events = {}
    event_wrappers = driver.find_elements(By.CSS_SELECTOR, ".eventhelper_ewrapper__A_RGO")
    for ew in event_wrappers:
        try:
            event_name = ew.find_element(By.CSS_SELECTOR, ".tooltips_ttable_heading__DK4_X").text.strip()
            grid = ew.find_element(By.CSS_SELECTOR, ".eventhelper_egrid__F3rTP")
            cells = grid.find_elements(By.CSS_SELECTOR, ".eventhelper_ecell__B48KX")
            event_data = {}
            for i in range(0, len(cells), 2):
                label = cells[i].text.strip()
                effect = cells[i+1].text.strip()
                event_data[label] = effect
            events[event_name] = event_data
        except Exception as e:
            print(f"Error parsing event: {e}")
    
    add_events(events)
    print(f"Added {len(events)} events from Support ID {support_id}.")

# Save unique events to JSON
with open("all_support_events.json", "w", encoding="utf-8") as f:
    json.dump(unique_events, f, indent=2, ensure_ascii=False)

print("\nSaved all unique support events to all_support_events.json")

driver.quit()
