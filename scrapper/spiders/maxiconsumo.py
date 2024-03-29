import os
import re
import scrapy
import time
from ..items import MaxiconsumoItem
from selenium import webdriver
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait


class MaxiconsumoSpider(scrapy.Spider):
    name = 'maxiconsumo'
    category = ""
    max_pages = 0
    allowed_domains = ['https://maxiconsumo.com/sucursal_burzaco/']
    driver = None
    login_url = 'https://maxiconsumo.com/sucursal_burzaco/customer/account/login/'
    custom_settings = {
        'FEED_EXPORT_FIELDS': [
            "product_name",
            "code",
            "product_url",
            "bundle_price",
            "unit_price"
        ]
    }

    def __init__(self, category, max_pages):
        self.category = category
        self.max_pages = max_pages

        self.username = os.environ["MAXICONSUMO_USERNAME"]
        self.password = os.environ["MAXICONSUMO_PASSWORD"]
        super().__init__()

    def start_requests(self):
        self.login()
        url = 'http://quotes.toscrape.com/'
        yield scrapy.Request(url=url, callback=self.parse)

    def login(self):
        options = webdriver.ChromeOptions()
        options.add_argument("--headless")
        self.driver = webdriver.Chrome(ChromeDriverManager().install(), options=options)
        self.driver.get(self.login_url)

        wait = WebDriverWait(self.driver, 5)
        user_input = wait.until(EC.presence_of_element_located((By.XPATH, '//*[@id="email"]')))
        user_input.send_keys(self.username)

        password_input = self.driver.find_element(By.XPATH, '//*[@id="pass"]')
        password_input.send_keys(self.password)

        enter_button = self.driver.find_element(By.XPATH, '//*[@id="send2"]')
        enter_button.click()

    def parse(self, response):
        urls = self.generate_paged_urls('https://maxiconsumo.com/sucursal_burzaco/{category}.html?p={p}&product_list_limit=96', self.category, int(self.max_pages))

        for url in urls:
            self.driver.get(url)
            wait = WebDriverWait(self.driver, 5)
            wait.until(EC.presence_of_element_located((By.XPATH, '//*[@id="page-title-heading"]/span')))

            products_list = self.driver.find_elements_by_class_name('list-item')
            for product in products_list:
                product_element = product.find_element_by_class_name('product-item-link')
                product_name = product_element.text
                product_href = product_element.get_attribute('href')
                prices = self.search_and_extract_product_price(product)
                bundle_price = prices[0]
                unit_price = prices[1]
                code = self.get_code_from_url(product_href)

                item = self.create_item(product_name, code, product_href, bundle_price, unit_price)
                yield item

        # Terminate Session
        time.sleep(3)
        self.driver.stop_client()
        self.driver.close()

    def generate_paged_urls(self, base_url, category: str, max_pages_num: int):
        urls_list = []

        for num in range(1, max_pages_num + 1):
            url = base_url.replace("{p}", str(num))
            url = url.replace("{category}", category)
            urls_list.append(url)
        return urls_list

    def search_and_extract_product_price(self, product):
        product_prices = product.find_elements_by_class_name('price-box')
        bundle_price = "$0"
        unit_price = "$0"

        for product_price in product_prices:
            label = product_price.find_element_by_class_name('price-label').text
            price = product_price.find_element_by_class_name('price').text
            if label == "Precio unitario por bulto cerrado":
                bundle_price = price
            if label == "Precio unitario":
                unit_price = price
        return (bundle_price, unit_price)

    def create_item(self, product_name, code, product_href, bundle_price, unit_price):
        item = MaxiconsumoItem()
        item["product_name"] = product_name
        item["code"] = code
        item["product_url"] = product_href
        item["bundle_price"] = bundle_price
        item["unit_price"] = unit_price
        return item

    def get_code_from_url(self, url):
        code = ""
        result = re.search(r'/s/(.*?)/category/', url)
        if result is not None:
            name = result.group(1)
            splitted_name = name.split('-')
            code = splitted_name[-1]

        return code
