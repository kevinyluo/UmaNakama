import time
import json
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import re

# Symbols to strip: stars, circles, music notes, hearts, bullets, diamonds, etc.
_STARLIKE = r"[☆★○●♪♫•※◎◇◆■□▼▲♥♡❀✿✸✦✧✪✩✫✬✭✮✯]"
def _strip_parens(text: str) -> str:
    # remove any (...) groups, possibly multiple occurrences
    return re.sub(r"\([^)]*\)", "", text)

def clean_text(text: str) -> str:
    if not text:
        return ""
    t = _strip_parens(text)
    t = re.sub(_STARLIKE, "", t)
    # normalize whitespace (keep newlines if you want; tidy around them)
    t = re.sub(r"[ \t]+", " ", t)         # collapse spaces/tabs
    t = re.sub(r"\s+\n", "\n", t)         # remove trailing spaces before newlines
    t = re.sub(r"\n\s+", "\n", t)         # remove leading spaces after newlines
    return t.strip()

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

path = "C:\\Users\\kevin\\Downloads\\chromedriver-win64 (1)\\chromedriver-win64\\chromedriver.exe"
URL = "https://gametora.com/umamusume/training-event-helper"

service = Service(executable_path=path)
driver = webdriver.Chrome(service=service)
driver.get(URL)

wait = WebDriverWait(driver, 10)


# Change senario to URA finals
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

# Open character select box
wait_and_click(driver, wait, "boxChar", By.ID, "Character select box")
time.sleep(1)

# Find all character containers (including the first "Remove" button)
characters = []
containers = driver.find_elements(By.CSS_SELECTOR, "div.sc-98a8819c-1.limvpr")
for c in containers:
    try:
        name_div = c.find_element(By.CSS_SELECTOR, "div.sc-98a8819c-2.iRNLFG")
        name = name_div.text.strip()
        characters.append((name, c))
    except Exception:
        continue

print(f"Found {len(characters)} characters (including 'Remove'). Skipping the first.")

unique_events = {}

def add_events(scraped_events):
    for event_name, event_data in scraped_events.items():
        if event_name not in unique_events:
            unique_events[event_name] = event_data

for name, container in characters[1:]:  # Skip first "Remove"
    print(f"\n--- Scraping: {name} ---")
    
    # Re-open character select box before clicking next character
    wait_and_click(driver, wait, "boxChar", By.ID, "Character select box")
    time.sleep(1)  # small delay for UI to update
    
    # Re-find the container because DOM changed
    containers = driver.find_elements(By.CSS_SELECTOR, "div.sc-98a8819c-1.limvpr")
    container = None
    for c in containers:
        try:
            name_div = c.find_element(By.CSS_SELECTOR, "div.sc-98a8819c-2.iRNLFG")
            if name_div.text.strip() == name:
                container = c
                break
        except Exception:
            pass
    
    if container is None:
        print(f"Could not find container for {name} after re-opening char box.")
        continue

    driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", container)
    
    try:
        driver.execute_script("arguments[0].click();", container)
    except Exception as e:
        print(f"JS click failed for {name}: {e}")
        container.click()
    
    time.sleep(1)  # wait for event data to load
    
    # Scrape events
    events = {}
    event_wrappers = driver.find_elements(By.CSS_SELECTOR, ".eventhelper_ewrapper__A_RGO")
    for ew in event_wrappers:
        try:
            event_name = clean_text(ew.find_element(By.CSS_SELECTOR, ".tooltips_ttable_heading__DK4_X").text)
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
    print(f"Added {len(events)} events from {name}.")

# Save unique events to JSON
with open("all_training_events.json", "w", encoding="utf-8") as f:
    json.dump(unique_events, f, indent=2, ensure_ascii=False)

print("\nSaved all unique training events to all_training_events.json")

driver.quit()
