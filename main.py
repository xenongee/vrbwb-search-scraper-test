import random
import time
import pandas
from urllib.parse import urlencode
from playwright.sync_api import sync_playwright
from playwright_stealth import Stealth

HEADLESS = True
BASE_URL = "https://www.wildberries.ru"
SEARCH_PARAMS = {
    "sort": "popular",
    "search": "пальто из натуральной шерсти",
}
MADEBY = "Россия"
SEARCH_URL = f"{BASE_URL}/catalog/0/search.aspx?{urlencode(SEARCH_PARAMS)}"
MAX_PRODUCTS_COUNT = 100
# MAX_PRODUCTS_COUNT = 5 # for testing
LOCATES = {
    # antibot
    "antibot_title": ".support-title",
    "antibot_subtitle": ".support-subtitle",

    # Catalog
    "catalog_list": "#catalog .product-card-list",
    "catalog_item": ".product-card",
    "catalog_item_link": "a.product-card__link",

    # Product page general
    "product_article": ".product-page tr:has-text('Артикул') button span",
    "product_title": ".product-page [class*='productTitle']",

    # Product page prices
    "product_wallet_price": "[class*='priceBlockWalletPrice'] h2",
    "product_final_price": "[class*='priceBlockFinalPrice']",

    # Product characteristics and description
    "product_characteristics_btn": "[class*='options'] button:has-text('характеристики')",
    "product_characteristics_modal": "section[data-testid='product_additional_information']",
    "product_description": "[class*='mo-modal__wrapper'] #section-description p",

    # Product images
    "product_images_slider": ".swiper-wrapper img",

    # Product seller
    "product_seller_name": "[class*='sellerInfoNameDefaultText']",
    "product_seller-user_name": "[class*='SellerUserButtonTitle'] span",
    "product_seller_url": "a[class*='sellerInfoButtonLink']",

    # Product sizes
     "product_size_btn_more": "li[class*='sizesListItemMore'] button",
     "product_sizes_list": "ul[class*='sizesList']",

    #Product stock and reviews
    "product_stock_count": "[class*='qtyTrigger'] span",
    "product_no_reviews": ".non-comments",
    "product_rating": ".user-opinion__rating-numb",
    "product_review_count": ".user-opinion__text",
}
PRICE_TYPE = "wallet_price" # wallet_price or final_price
COLUMNS_MAP = {
    "url": "Ссылка на товар",
    "article": "Артикул",
    "name": "Название",
    PRICE_TYPE: "Цена",
    "description": "Описание",
    "images_urls": "Ссылки на изображения",
    "characteristics": "Все характеристики",
    "seller_name": "Название селлера",
    "seller_url": "Ссылка на селлера",
    "sizes": "Размеры товара",
    "stock_count": "Остатки по товару (число)",
    "rating": "Рейтинг",
    "review_count": "Количество отзывов",
}
FILE_NAME = "wb-scraped.xlsx"
FILE_NAME_FILTERED = "wb-scraped-filtered.xlsx"

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

def collect_products_links(pw_page, max_products_count=MAX_PRODUCTS_COUNT):
    links_collection = set()
    scroll_step = 500
    get_new_items_attempts = 0

    catalog_items = pw_page.locator(f"{LOCATES["catalog_list"]} {LOCATES["catalog_item"]}")
    catalog_item_link = catalog_items.locator(LOCATES["catalog_item_link"])

    print("Scrolling...")

    while len(links_collection) < max_products_count:
        pw_page.mouse.wheel(0, scroll_step)
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
            print(f"Found {len(links_collection)}/{max_products_count} product links...")

        if get_new_items_attempts > 10:
            print("Failed to get new items after 10 attempts")
            break

    return list(links_collection)

def clean_text(text):
    if not text:
        return text
    return text.replace("\xa0", " ").strip()

def extract_digits(text):
    if not text:
        return 0
    digits = ''.join(filter(str.isdigit, text))
    return int(digits) if digits else 0

def extract_rating(text):
    if not text:
        return 0.0
    try:
        return float(text.replace(",", ".").strip())
    except:
        return 0.0

def scrape_product_page(page, url):
    product_data = {
        "url": url,
        "article": "",
        "name": "",
        "wallet_price": 0,
        "final_price": 0,
        "description": "",
        "images_urls": "",
        "characteristics": {},
        "seller_name": "",
        "seller_url": "",
        "sizes": "",
        "stock_count": "",
        "rating": 0.0,
        "review_count": 0,
    }

    # Load page and check loading
    try:
        page.goto(url, wait_until="domcontentloaded")
        page.wait_for_selector(LOCATES["product_title"], timeout=15000)
    except Exception as e:
        print(f"Error loading product page: {url}. Details: {e}")
        return None

    # Characteristics
    try:
        characteristics_btn_locator = page.locator(LOCATES["product_characteristics_btn"]).first
        if characteristics_btn_locator.is_visible():
            characteristics_btn_locator.scroll_into_view_if_needed()
            time.sleep(0.5)
            characteristics_btn_locator.click(force=True)
            try:
                page.locator(f"{LOCATES['product_characteristics_modal']} table").first.wait_for(timeout=5000)
            except: pass

    except Exception as e:
        print(f"Error: Failed to open characteristics modal: {url}. Details: {e}")

    try:
        tables = page.locator(f"{LOCATES['product_characteristics_modal']} table").all()
        data = {}

        for table in tables:
            rows = table.locator("tr").all()
            for row in rows:
                key_el = row.locator("th").first
                val_el = row.locator("td").first

                if key_el.is_visible() and val_el.is_visible():
                    key = clean_text(key_el.inner_text())
                    val = clean_text(val_el.inner_text())
                    if key and val:
                        data[key] = val

        description_locator = page.locator(LOCATES["product_description"]).first
        if description_locator.is_visible():
            product_data["description"] = clean_text(description_locator.inner_text())

        product_data["characteristics"] = data
    except Exception as e:
        print(f"Error: Failed to scrape product characteristics: {url}. Details: {e}")

    # Title
    try:
        product_data["name"] = page.locator(LOCATES["product_title"]).inner_text()
    except Exception as e:
        print(f"Error: Failed to parse product title: {url}. Details: {e}")

    # Article
    try:
        product_data["article"] = page.locator(LOCATES["product_article"]).inner_text()
    except Exception as e:
        print(f"Error: Failed to parse product article: {url}. Details: {e}")

    # Prices
    try:
        wallet_price_locator = page.locator(LOCATES["product_wallet_price"]).first
        final_price_locator = page.locator(LOCATES["product_final_price"]).first

        if wallet_price_locator.is_visible():
            product_data["wallet_price"] = extract_digits(wallet_price_locator.inner_text())

        if final_price_locator.is_visible():
            product_data["final_price"] = extract_digits(final_price_locator.inner_text())
    except Exception as e:
        print(f"Error: Failed to parse product price: {url}. Details: {e}")

    # Images
    try:
        imgs = []
        swiper_elements_locator = page.locator(LOCATES["product_images_slider"]).all()

        for img in swiper_elements_locator:
            src = img.get_attribute("src")
            if src:
                hq_src = src.replace("/tm/", "/big/").replace("/c246x328/", "/big/")
                imgs.append(hq_src)

        product_data["images_urls"] = ", ".join(list(set(imgs)))
    except Exception as e:
        print(f"Error: Failed to parse product images: {url}. Details: {e}")

    # Seller
    try:
        seller_default_locator = page.locator(LOCATES["product_seller_name"]).first
        seller_user_locator = page.locator(LOCATES["product_seller-user_name"]).first

        if seller_default_locator.is_visible():
            product_data["seller_name"] = seller_default_locator.inner_text()
        elif seller_user_locator.is_visible():
            product_data["seller_name"] = f"{seller_user_locator.inner_text()}"
            # product_data["seller_name"] = f"{seller_user_locator.inner_text()} (Покупатель WB)"

        seller_url_locator = page.locator(LOCATES["product_seller_url"]).first
        if seller_url_locator.is_visible():
            seller_href = seller_url_locator.get_attribute("href")
            if seller_href:
                product_data["seller_url"] = f"{BASE_URL}{seller_href}"
    except Exception as e:
        print(f"Error: Failed to parse product seller name or seller url: {url}. Details: {e}")

    # Sizes
    try:
        product_size_btn_more_locator = page.locator(LOCATES["product_size_btn_more"]).first
        if product_size_btn_more_locator.is_visible():
            product_size_btn_more_locator.click(force=True)
            time.sleep(0.5)

        sizes_list = []
        items = page.locator(f"{LOCATES['product_sizes_list']} button").all()

        for item in items:
            text = item.inner_text().replace("\n", " RU: ").strip()
            sizes_list.append(clean_text(text))

        product_data["sizes"] = ", ".join(list(set(sizes_list)))
    except Exception as e:
        print(f"Error: Failed to parse product sizes: {url}. Details: {e}")

    # Stock Count
    try:
        stock_count_locator = page.locator(LOCATES["product_stock_count"]).first
        if stock_count_locator.is_visible():
            product_data["stock_count"] = extract_digits(stock_count_locator.inner_text())
    except Exception as e:
        print(f"Error: Failed to parse product stock count: {url}. Details: {e}")

    # Rating and Reviews
    try:
        if not page.locator(LOCATES["product_no_reviews"]).first.is_visible():
            rating_text_locator = page.locator(LOCATES["product_rating"]).first
            review_count_text_locator = page.locator(LOCATES["product_review_count"]).first

            if rating_text_locator.is_visible():
                product_data["rating"] = extract_rating(rating_text_locator.inner_text())

            if review_count_text_locator.is_visible():
                product_data["review_count"] = extract_digits(review_count_text_locator.inner_text())
    except Exception as e:
        print(f"Error: Failed to parse product rating and reviews: {url}. Details: {e}")

    return product_data

def save_to_excel_simple(filename, data_list, columns_map):
    if not data_list:
        print("No data to save!")
        return

    dataframe = pandas.DataFrame(data_list)

    def clean_cell(data):
        if isinstance(data, dict):
            lines = []
            for key, value in data.items():
                line = f"{key}: {value}"
                lines.append(line)
            return "\n".join(lines)

        if isinstance(data, list):
            return ", ".join(map(str, data))

        return data

    dataframe = dataframe.map(clean_cell)

    dataframe = dataframe[list(columns_map.keys())]
    dataframe = dataframe.rename(columns=columns_map)

    dataframe.to_excel(filename, index=False)
    print(f"File saved: {filename} ({len(dataframe)} rows)")

# Filter products based on criteria
def is_specific_product(item):
    characteristic_items = item.get("characteristics", {})

    if not isinstance(characteristic_items, dict):
        return False

    country = ""
    for key, value in characteristic_items.items():
        if "страна" in key.lower():
            country = value
            break

    current_rating = float(item.get("rating", 0))
    current_price = int(item.get(PRICE_TYPE, 0))

    return (
        current_rating >= 4.5 and
        current_price < 10000 and
        MADEBY.lower() in country.lower()
    )

def main():
    print(f"Work with {SEARCH_URL}")

    with Stealth().use_sync(sync_playwright()) as p:
        browser = p.chromium.launch(headless=HEADLESS)
        page = browser.new_page()

        try:
            page.goto(SEARCH_URL)

            ### Check antibot
            if check_catalog_is_loaded(page):
                ### Collect links
                links = collect_products_links(page, MAX_PRODUCTS_COUNT)
                print(f"Collected {len(links)} product links: {links[:MAX_PRODUCTS_COUNT]}")

                ### Parse products from links
                products_data = []
                for i, link in enumerate(links[:MAX_PRODUCTS_COUNT]):
                    print(f"[{i+1}/{len(links)}] Product: {link}")
                    data = scrape_product_page(page, link)
                    if data:
                        products_data.append(data)

                    time.sleep(random.uniform(1, 3)) # Delay between product page requests

            else:
                print("Exiting...")
                return

        except Exception as e:
            print(f"Error: {e}")
        finally:
            browser.close()

    ### Save results to Excel
    if products_data:
        save_to_excel_simple(FILE_NAME, products_data, COLUMNS_MAP)

        filtered_data = []
        for item in products_data:
            if is_specific_product(item):
                filtered_data.append(item)

        print(f"Filtered products: {len(filtered_data)}")
        if filtered_data:
            save_to_excel_simple(FILE_NAME_FILTERED, filtered_data, COLUMNS_MAP)
        else:
            print("Filtered list is empty, no file created.")

if __name__ == "__main__":
    main()
