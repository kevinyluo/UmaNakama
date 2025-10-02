import time
import json
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import re
import os

# Symbols to strip from EVENT TITLES (not character names)
_STARLIKE = r"[☆★○●♪♫•※◎◇◆■□▼▲♥♡❀✿✸✦✧✪✩✫✬✭✮✯]"
# Remove (...) or （…） blocks in EVENT TITLES
_PARENS_BOTH = r"[\(\（][^\)\）]*[\)\）]"

def clean_text(text: str) -> str:
    """Clean event title text (NOT used for character names)."""
    if not text:
        return ""
    t = re.sub(_PARENS_BOTH, "", text)
    t = re.sub(_STARLIKE, "", t)
    # normalize whitespace around newlines
    t = re.sub(r"[ \t]+", " ", t)
    t = re.sub(r"\s+\n", "\n", t)
    t = re.sub(r"\n\s+", "\n", t)
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

path = r"C:\Users\kevin\Downloads\chromedriver-win64 (1)\chromedriver-win64\chromedriver.exe"
URL = "https://gametora.com/umamusume/training-event-helper"

service = Service(executable_path=path)
driver = webdriver.Chrome(service=service)
driver.get(URL)

wait = WebDriverWait(driver, 10)

# Career -> URA Finals
wait_and_click(driver, wait, "//div[@class='compatibility_box_caption__IT3km' and text()='Career']", By.XPATH, "'Career' box")
wait_and_click(driver, wait, "//div[@class='sc-9ae1b094-1 hwTozI']/span[text()='URA Finals']", By.XPATH, "'URA Finals' option")

# Settings
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

# Open character select
wait_and_click(driver, wait, "boxChar", By.ID, "Character select box")
time.sleep(1)

# Collect all characters (includes first "Remove")
characters = []
containers = driver.find_elements(By.CSS_SELECTOR, "div.sc-98a8819c-1.limvpr")
for c in containers:
    try:
        name_div = c.find_element(By.CSS_SELECTOR, "div.sc-98a8819c-2.iRNLFG")
        name_raw = name_div.text.strip()  # keep EXACT as shown on site
        characters.append((name_raw, c))
    except Exception:
        continue

print(f"Found {len(characters)} characters (including 'Remove'). Skipping the first.")

# Outputs
trainee_events_by_raw = {}   # key = RAW name, value = events dict
raw_name_set = set()         # collect raw names

for name_raw, _container in characters[1:]:  # Skip first "Remove"
    print(f"\n--- Scraping: {name_raw} ---")
    raw_name_set.add(name_raw)

    # Re-open box and re-find this character by RAW name (DOM changes)
    wait_and_click(driver, wait, "boxChar", By.ID, "Character select box")
    time.sleep(1)

    containers = driver.find_elements(By.CSS_SELECTOR, "div.sc-98a8819c-1.limvpr")
    target = None
    for c in containers:
        try:
            name_div = c.find_element(By.CSS_SELECTOR, "div.sc-98a8819c-2.iRNLFG")
            if name_div.text.strip() == name_raw:
                target = c
                break
        except Exception:
            pass

    if target is None:
        print(f"Could not find container for {name_raw} after re-opening char box.")
        continue

    driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", target)
    try:
        driver.execute_script("arguments[0].click();", target)
    except Exception as e:
        print(f"JS click failed for {name_raw}: {e}")
        target.click()

    time.sleep(1)

    # Scrape this character's events (event titles cleaned, effects left as-is)
    events = {}
    event_wrappers = driver.find_elements(By.CSS_SELECTOR, ".eventhelper_ewrapper__A_RGO")
    for ew in event_wrappers:
        try:
            event_title_raw = ew.find_element(By.CSS_SELECTOR, ".tooltips_ttable_heading__DK4_X").text
            event_name = clean_text(event_title_raw)  # clean ONLY event title
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

    # Use RAW name as the key
    trainee_events_by_raw[name_raw] = events
    print(f"Added {len(events)} events from {name_raw}.")

# Write events keyed by RAW name
with open("trainee_events_by_character.json", "w", encoding="utf-8") as f:
    json.dump(trainee_events_by_raw, f, indent=2, ensure_ascii=False)

# Write raw names exactly as seen (unique, sorted)
with open("trainee_names.json", "w", encoding="utf-8") as f:
    json.dump(sorted(raw_name_set), f, indent=2, ensure_ascii=False)

print("\nSaved events to trainee_events_by_character.json")
print("Saved raw names to trainee_names.json")

driver.quit()
