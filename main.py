import random
import time
import pandas
from urllib.parse import urlencode
from playwright.sync_api import sync_playwright
from playwright_stealth import Stealth

HEADLESS = False
MAX_PRODUCTS_COUNT = 60
BASE_URL = "https://www.wildberries.ru"
SEARCH_PARAMS = {
    "sort": "popular",
    "search": "пальто из натуральной шерсти",
}
SEARCH_URL = f"{BASE_URL}/catalog/0/search.aspx?{urlencode(SEARCH_PARAMS)}"

PRICE_TYPE = "final_price" # wallet_price or final_price
FILTER_CONTRY = "Россия"
FILTER_MIN_RATING = 4.5
FILTER_MAX_PRICE = 1000

FILE_NAME = "wb-scraped.xlsx"
FILE_NAME_FILTERED = "wb-scraped-filtered.xlsx"

LOCATES = {
    # Antibot page
    "antibot_title": ".support-title",
    "antibot_subtitle": ".support-subtitle",

    # Catalog page
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
    "product_characteristics_btn": "[class*='options'] [class*='btnDetail'], [class*='options'] [class*='allCharsResaleButton']",
    "product_characteristics_table": "[class*='detailsModalOverlay'] section[data-testid='product_additional_information'] table",
    "product_characteristics_description": "[class*='detailsModalOverlay'] #section-description [class*='descriptionText']",

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

def check_catalog_is_loaded(page):
    timeout = 15
    start_time = time.time()

    while (time.time() - start_time) <= timeout:
        catalog_list = page.locator(LOCATES["catalog_list"])
        if catalog_list.is_visible():
            count = catalog_list.locator(LOCATES["catalog_item"]).count()
            if catalog_list.count() > 0:
                print(f"> Catalog loaded! ({count} items)")
                return True

        has_antibot_title = "Почти готово..." in page.title()
        has_antibot_page_title = page.locator(LOCATES["antibot_title"], has_text="Что-то не так...").is_visible()
        has_antibot_page_subtitle = page.locator(LOCATES["antibot_subtitle"], has_text="Подозрительная активность с вашего IP").is_visible()

        if has_antibot_title and (has_antibot_page_title or has_antibot_page_subtitle):
            print("> Antibot page detected...")
            return False

        time.sleep(.5)

    print("> Timeout reached. Catalog not loaded. Maybe blocked by antibot...")
    return False

def collect_product_links(pw_page, max_products_count=MAX_PRODUCTS_COUNT):
    links_collection = set()
    scroll_step = 500
    get_new_items_attempts = 0

    catalog_items = pw_page.locator(f"{LOCATES["catalog_list"]} {LOCATES["catalog_item"]}")
    catalog_item_link = catalog_items.locator(LOCATES["catalog_item_link"])

    print("> Scrolling...")

    while len(links_collection) <= max_products_count:
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
            print(f"> Found {len(links_collection)}/{max_products_count} product links...")

        if get_new_items_attempts > 10:
            print("> Failed to get new items after 10 attempts")
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

def open_characteristics_modal(page):
    characteristics_buttons_locator = page.locator(LOCATES["product_characteristics_btn"]).all()

    for ch_button in characteristics_buttons_locator:
        if not ch_button.is_visible():
            continue

        try:
            time.sleep(.5)
            ch_button.scroll_into_view_if_needed()
            ch_button.click(timeout=5000)
            page.wait_for_selector(LOCATES['product_characteristics_table'], timeout=5000)
            return True
        except Exception as e:
            print("> Failed to open characteristics modal, trying another button. Details: {e}")
            continue

    return False

def parse_prices(page):
    wallet_price_selector = page.locator(LOCATES["product_wallet_price"]).first
    final_price_selector = page.locator(LOCATES["product_final_price"]).first

    wallet_price_selector.wait_for(state='visible', timeout=5000)
    final_price_selector.wait_for(state='visible', timeout=5000)

    wallet_price = extract_digits(wallet_price_selector.inner_text())
    final_price = extract_digits(final_price_selector.inner_text())

    if wallet_price <= 0:
        wallet_price = final_price

    return wallet_price, final_price

def parse_characteristics_table(page):
    char_tables = page.locator(LOCATES['product_characteristics_table']).all()
    data = {}

    for table in char_tables:
        rows = table.locator("tr").all()
        for row in rows:
            key_el = row.locator("th").first
            val_el = row.locator("td").first

            if key_el.is_visible() and val_el.is_visible():
                key = clean_text(key_el.inner_text())
                val = clean_text(val_el.inner_text())
                if key and val:
                    data[key] = val

    return data

def parse_characteristics_desc(page):
    char_desciption_locator = page.locator(LOCATES["product_characteristics_description"]).first

    if char_desciption_locator.is_visible():
        return clean_text(char_desciption_locator.inner_text())

def parse_images(page):
    imgs = []
    swiper_elements_locator = page.locator(LOCATES["product_images_slider"]).all()

    for img_item in swiper_elements_locator:
        src = img_item.get_attribute("src")
        if src:
            hq_src = src.replace("/tm/", "/big/").replace("/c246x328/", "/big/")
            imgs.append(hq_src)

    return ", ".join(list(set(imgs)))

def parse_seller_info(page):
    seller_default_locator = page.locator(LOCATES["product_seller_name"]).first
    seller_user_locator = page.locator(LOCATES["product_seller-user_name"]).first

    if seller_default_locator.is_visible():
        seller_name = seller_default_locator.inner_text()
    elif seller_user_locator.is_visible():
        seller_name = f"{seller_user_locator.inner_text()}"
        # product_data["seller_name"] = f"{seller_user_locator.inner_text()} (Покупатель WB)"

    seller_url_locator = page.locator(LOCATES["product_seller_url"]).first
    if seller_url_locator.is_visible():
        seller_href = seller_url_locator.get_attribute("href")
        if seller_href:
            seller_url = f"{BASE_URL}{seller_href}"

    return seller_name, seller_url

def parse_product_sizes(page):
    product_size_btn_more_locator = page.locator(LOCATES["product_size_btn_more"]).first
    if product_size_btn_more_locator.is_visible():
        product_size_btn_more_locator.click(force=True)
        time.sleep(.5)

    sizes_list = []
    items = page.locator(f"{LOCATES['product_sizes_list']} button").all()

    for item in items:
        text = item.inner_text().replace("\n", " RU: ").strip()
        sizes_list.append(clean_text(text))

    return ", ".join(list(set(sizes_list)))

def parse_stock_count(page):
    stock_count_locator = page.locator(LOCATES["product_stock_count"]).first
    if stock_count_locator.is_visible():
        return extract_digits(stock_count_locator.inner_text())

def parse_rating_and_review_count(page):
    if not page.locator(LOCATES["product_no_reviews"]).first.is_visible():
        rating_text_locator = page.locator(LOCATES["product_rating"]).first
        review_count_text_locator = page.locator(LOCATES["product_review_count"]).first

        if rating_text_locator.is_visible():
            product_rating = extract_rating(rating_text_locator.inner_text())

        if review_count_text_locator.is_visible():
            product_review_count = extract_digits(review_count_text_locator.inner_text())

    return product_rating, product_review_count

def scrape_product_page(page, url):
    # Load page and check loading
    try:
        page.goto(url, wait_until="domcontentloaded")
        page.wait_for_selector(LOCATES["product_title"], timeout=5000)
        time.sleep(.5)
    except Exception as e:
        print(f"> Error loading product page: {url}. Details: {e}")
        return None

    product_data = {
        "url": url,
        "article": page.locator(LOCATES["product_article"]).inner_text(),
        "name": page.locator(LOCATES["product_title"]).inner_text(),
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

    product_data["wallet_price"], product_data["final_price"] = parse_prices(page)
    product_data["seller_name"], product_data["seller_url"] = parse_seller_info(page)
    product_data["rating"], product_data["review_count"] = parse_rating_and_review_count(page)
    product_data["images_urls"] = parse_images(page)
    product_data['sizes'] = parse_product_sizes(page)
    product_data["stock_count"] = parse_stock_count(page)

    modal_opened = open_characteristics_modal(page)

    if modal_opened:
        product_data["characteristics"] = parse_characteristics_table(page)
        product_data["description"] = parse_characteristics_desc(page)

    return product_data

def save_to_excel(filename, data, columns):
    if not data:
        print("! Error: No data to save!")
        return

    dataframe = pandas.DataFrame(data)

    def transform_to_strings(data):
        if isinstance(data, dict):
            lines = []
            for key, value in data.items():
                line = f"{key}: {value}"
                lines.append(line)
            return "\n".join(lines)

        if isinstance(data, list):
            return ", ".join(map(str, data))

        return data

    dataframe = dataframe.map(transform_to_strings)
    dataframe = dataframe[list(columns.keys())]
    dataframe = dataframe.rename(columns=columns)
    dataframe.to_excel(filename, index=False)
    print(f"File saved: {filename} ({len(dataframe)} rows)")

# Filter products based on criteria
def filter_products(products):
    filtered = []

    for item in products:
        chars = item.get("characteristics", {})
        if not isinstance(chars, dict):
            continue

        country = ""
        for key, value in chars.items():
            if "страна" in key.lower():
                country = value
                break

        rating = float(item.get("rating", 0))
        price = int(item.get(PRICE_TYPE, 0))

        if (rating >= FILTER_MIN_RATING and
            price < FILTER_MAX_PRICE and
            FILTER_CONTRY.lower()) in country.lower():
            filtered.append(item)

    return filtered

def main():
    print(f"> Work with {SEARCH_URL}")

    with Stealth().use_sync(sync_playwright()) as p:
        browser = p.chromium.launch(headless=HEADLESS)
        page = browser.new_page()

        try:
            page.goto(SEARCH_URL)

            ### Check antibot
            if not check_catalog_is_loaded(page):
                print("! Failed to load catalog. Exiting...")
                return

            ### Collect links
            product_links = collect_product_links(page, MAX_PRODUCTS_COUNT)[:MAX_PRODUCTS_COUNT]
            print(f"> Collected {len(product_links)} product links")

            ### Parse products from links
            products_data = []
            for i, link in enumerate(product_links):
                print(f"[{i+1}/{len(product_links)}] Product: {link}")
                data = scrape_product_page(page, link)
                if data:
                    products_data.append(data)

                time.sleep(random.uniform(1, 3))

        except Exception as e:
            print(f"Error: {e}")
        finally:
            browser.close()

    ### Save results to Excel
    if products_data:
        save_to_excel(FILE_NAME, products_data, COLUMNS_MAP)

        filtered_data = filter_products(products_data)
        print(f"Filtered products: {len(filtered_data)}")

        if filtered_data:
            save_to_excel(FILE_NAME_FILTERED, filtered_data, COLUMNS_MAP)

if __name__ == "__main__":
    main()
