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

def parse_tooltip(tooltip):
    data = {
        "img_src": "",
        "description_game": "",
        "description_detailed": "",
        "rarity": "",
        "activation": "",
        "base_cost": "",
        "conditons": "",
        "base_duration": "",
        "effect": ""
    }

    try:
        img = tooltip.find_element(By.CSS_SELECTOR, "img")
        data["img_src"] = img.get_attribute("src").replace("https://gametora.com", "")

        rows = tooltip.find_elements(By.CLASS_NAME, "tooltips_tooltip_line__OStyx")
        for row in rows:
            text = row.text.strip()
            if text.startswith("Description (in-game):"):
                data["description_game"] = text.replace("Description (in-game):", "").strip()
            elif text.startswith("Description (detailed):"):
                data["description_detailed"] = text.replace("Description (detailed):", "").strip()
            elif text.startswith("Rarity:"):
                data["rarity"] = text.replace("Rarity:", "").strip()
            elif text.startswith("Activation:"):
                data["activation"] = text.replace("Activation:", "").strip()
            elif text.startswith("Base cost:"):
                data["base_cost"] = text.replace("Base cost:", "").strip()
            elif text.startswith("Conditions:"):
                try:
                    condition_div = row.find_element(By.TAG_NAME, "div")
                    data["conditons"] = condition_div.text.strip()
                except:
                    pass
            elif text.startswith("Base duration:"):
                data["base_duration"] = text.replace("Base duration:", "").strip()
            elif text.startswith("Effect:"):
                data["effect"] = text.replace("Effect:", "").strip()
    except Exception as e:
        print("Error parsing tooltip:", e)

    return data

# Setup
path = "C:\\Users\\kevin\\Downloads\\chromedriver-win64\\chromedriver-win64\\chromedriver.exe"
URL = "https://gametora.com/umamusume/skills"

service = Service(executable_path=path)
driver = webdriver.Chrome(service=service)
driver.get(URL)
wait = WebDriverWait(driver, 10)
output = {}

# Get visible skill rows (excluding hidden)
containers = driver.find_elements(By.CSS_SELECTOR, ".skills_table_row_ja__XXxOj:not(.skills_hidden__8r0Tb)")
print(f"Found {len(containers)} visible skill containers")

for container in containers:
    try:
        skill_name = container.find_element(By.CSS_SELECTOR, ".skills_table_jpname__5TTkO").text.strip()
        if not skill_name:
            continue

        print(f"\n--- Scraping: {skill_name} ---")
        more_button = container.find_element(By.CSS_SELECTOR, "span.utils_linkcolor__rvv3k[aria-expanded='false']")
        driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", more_button)
        driver.execute_script("arguments[0].click();", more_button)
        time.sleep(0.3)

        tooltip = WebDriverWait(driver, 5).until(
            EC.presence_of_element_located((By.CLASS_NAME, "skills_skill_tooltip__JIWMZ"))
        )
        output[skill_name] = parse_tooltip(tooltip)

        # Close tooltip
        driver.execute_script("arguments[0].click();", more_button)
        time.sleep(0.2)

    except Exception as e:
        print(f"Failed scraping skill: {e}")
        continue

# Save JSON
with open("parsed_skills.json", "w", encoding="utf-8") as f:
    json.dump(output, f, indent=2, ensure_ascii=False)

print("\nSaved to parsed_skills.json")
driver.quit()
