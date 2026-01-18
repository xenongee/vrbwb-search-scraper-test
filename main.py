import unicodedata
from urllib.parse import urlencode
from playwright.sync_api import sync_playwright

BASE_URL = "https://www.wildberries.ru"
SEARCH_PARAMS = {
    "page": 1,
    "sort": "popular",
    "search": "пальто из натуральной шерсти",
    "priceU": "000;1000000"
}
SEARCH_URL = f"{BASE_URL}/catalog/0/search.aspx?{urlencode(SEARCH_PARAMS)}"

def check_antibot_page(page):
    # page.wait_for_timeout(5000)

    try:
        has_antibot_title = "Почти готово..." in page.title()

        antibot_page_title_locator = page.locator('.support-title')
        antibot_page_title_text = antibot_page_title_locator.text_content() if antibot_page_title_locator.count() > 0 else ""
        has_antibot_page_title = "Что-то не так..." in antibot_page_title_text

        antibot_page_subtitle_locator = page.locator('.support-subtitle')
        antibot_page_subtitle_text = antibot_page_subtitle_locator.text_content() if antibot_page_subtitle_locator.count() > 0 else ""
        has_antibot_page_subtitle = "Подозрительная активность с вашего IP" in unicodedata.normalize("NFKC", antibot_page_subtitle_text)

        return has_antibot_title and (has_antibot_page_title or has_antibot_page_subtitle)
    except Exception as e:
        print(f"Error checking antibot page: {e}")
        return False

def main():
    print(f"Work with {SEARCH_URL}");

    with sync_playwright() as p:
        browser_args = [
            '--start-maximized',
            '--disable-blink-features=AutomationControlled'
        ]
        browser = p.chromium.launch(headless=False, args=browser_args)

        context = browser.new_context(
            viewport={'width': 1920, 'height': 1032},
            java_script_enabled=True
        )

        page = context.new_page()

        try:
            page.goto(SEARCH_URL)

            attempts = 5
            for i in range(attempts):
                page.wait_for_timeout(1000)
                print(f"Antibot check ({i + 1}/{attempts})...")
                if check_antibot_page(page):
                    print("Antibot detected!")
                    return

            try:
                page.screenshot(path=f'screenshot.jpg')
            except Exception as e:
                print(f"Error: {e}")

        except Exception as e:
            print(f"Error: {e}")
        finally:
            browser.close()

if __name__ == "__main__":
    main()
