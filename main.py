import random
import time
from urllib.parse import urlencode
from playwright.sync_api import sync_playwright
from playwright_stealth import Stealth

BASE_URL = "https://www.wildberries.ru"
SEARCH_PARAMS = {
    "page": 1,
    "sort": "popular",
    "search": "пальто из натуральной шерсти",
    "priceU": "000;1000000"
}
SEARCH_URL = f"{BASE_URL}/catalog/0/search.aspx?{urlencode(SEARCH_PARAMS)}"
LOCATES = {
    "antibot_title": ".support-title",
    "antibot_subtitle": ".support-subtitle",
    "catalog_list": "#catalog .product-card-list",
    "catalog_item": ".product-card",
    "catalog_item_link": "a.product-card__link",
}
MAX_PRODUCTS_COUNT = 100

def check_catalog_is_loaded(page):
    timeout = 15000
    start_time = time.time()

    while (time.time() - start_time) < 1000 * timeout:
        catalog_list = page.locator(LOCATES["catalog_list"])
        if catalog_list.is_visible():
            count = catalog_list.locator(LOCATES["catalog_item"]).count()
            if catalog_list.count() > 0:
                print(f"Catalog loaded! ({count} items)")
                return True

        has_antibot_title = "Почти готово..." in page.title()
        has_antibot_page_title = page.locator(LOCATES["antibot_title"], has_text="Что-то не так...").is_visible()
        has_antibot_page_subtitle = page.locator(LOCATES["antibot_subtitle"], has_text="Подозрительная активность с вашего IP").is_visible()

        if has_antibot_title and (has_antibot_page_title or has_antibot_page_subtitle):
            print("Antibot page detected...")
            return False

        time.sleep(0.5)

    print("Timeout reached. Catalog not loaded. Maybe blocked by antibot...")
    return False

def collect_products_links(page):
    links_collection = set()
    scroll_step = 400

    catalog_items = page.locator(f"{LOCATES["catalog_list"]} {LOCATES["catalog_item"]}")
    catalog_item_link = catalog_items.locator(LOCATES["catalog_item_link"])

    while len(links_collection) < MAX_PRODUCTS_COUNT:
        page.mouse.wheel(0, scroll_step)
        time.sleep(random.uniform(0.3, 0.8))

        current_links = catalog_item_link.all()
        founded_links_count = len(links_collection)

        for i in current_links:
            try:
                href = i.get_attribute("href")
                links_collection.add(href)
            except:
                continue

        if len(links_collection) == founded_links_count:
            get_new_items_attempts += 1
        else:
            get_new_items_attempts = 0
            print(f"Found {len(links_collection)}/{MAX_PRODUCTS_COUNT} product links...")

        if get_new_items_attempts > 10:
            print("Failed to get new items after 10 attempts")
            break

    return list(links_collection)


def main():
    print(f"Work with {SEARCH_URL}");

    with Stealth().use_sync(sync_playwright()) as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        try:
            page.goto(SEARCH_URL)

            ### Check antibot
            if not check_catalog_is_loaded(page):
                return

            ### Collect links
            links = collect_products_links(page)

            ### Parse products from links

        except Exception as e:
            print(f"Error: {e}")
        finally:
            browser.close()

if __name__ == "__main__":
    main()
