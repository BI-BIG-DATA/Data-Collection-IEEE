from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
import pandas as pd
import time
import json
import logging
from urllib.parse import quote

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

class AcademicScraper:
    def __init__(self):
        self.driver = None
        self.results = []
        self.wait = None

    def setup_driver(self):
        options = webdriver.ChromeOptions()
        options.add_argument('--headless')
        options.add_argument('--disable-gpu')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--window-size=1920,1080')
        options.add_argument(
            'user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')

        self.driver = webdriver.Chrome(options=options)
        self.wait = WebDriverWait(self.driver, 20)

    def scrape_acm(self, query="machine learning", num_pages=5):
        """
        Scrape ACM Digital Library for "machine learning"
        """
        try:
            encoded_query = quote(query)
            base_url = f"https://dl.acm.org/action/doSearch?AllField={encoded_query}&language=fr"
            logging.info(f"Accessing ACM: {base_url}")

            self.driver.get(base_url)
            time.sleep(5)

            # Handle cookie consent if present
            try:
                cookie_button = self.wait.until(EC.element_to_be_clickable((By.CLASS_NAME, "cc-dismiss")))
                cookie_button.click()
                time.sleep(2)
            except:
                logging.info("No cookie banner found on ACM")

            for page in range(num_pages):
                logging.info(f"Processing ACM page {page + 1}")

                try:
                    # Wait for results to load
                    results = self.wait.until(EC.presence_of_all_elements_located(
                        (By.CLASS_NAME, "issue-item__content")))

                    for article in results:
                        try:
                            data = {
                                'journal': self._safe_get_text(article, '.epub-section__title'),  # Journal Title
                                'indexation': 'ACM',
                                'publication': self._safe_get_text(article, '.issue-item__publication-date'),  # Alternative for Publication date
                                'doi': self._safe_get_text(article, '.issue-item__doi'),  # DOI
                                'titre': self._safe_get_text(article, '.issue-item__title'),  # Article title
                                'chercheurs': self._safe_get_text(article, '.loa__author-name') or
                                              self._safe_get_text(article, '.issue-item__authors') or
                                              self._safe_get_text(article, '.author'),  # Authors - alternative
                                'laboratoires': self._safe_get_text(article, '.affiliation') or
                                                self._safe_get_text(article, '.institution') or
                                                self._safe_get_text(article, '.author-affiliation'),  # Affiliation - alternative
                                'abstract': self._safe_get_text(article, '.issue-item__abstract'),  # Abstract
                                'keywords': self._safe_get_text(article, '.keywords') or
                                            self._safe_get_text(article, '.keyword') or
                                            self._safe_get_text(article, '.issue-item__keyword'),  # Keywords - alternative
                            }
                            self.results.append(data)
                            logging.info(f"Successfully extracted ACM article: {data['titre'][:50]}...")

                        except Exception as e:
                            logging.error(f"Error processing ACM article: {e}")
                            continue

                    # Handle pagination
                    try:
                        next_button = self.wait.until(EC.element_to_be_clickable(
                            (By.CSS_SELECTOR, "a.pagination__btn--next")))
                        next_button.click()
                        time.sleep(3)
                    except:
                        logging.info("No more pages available on ACM")
                        break

                except TimeoutException:
                    logging.error(f"Timeout on ACM page {page + 1}")
                    break

        except Exception as e:
            logging.error(f"Error in ACM scraping: {e}")

    def _safe_get_text(self, element, selector):
        """Safely extract text from an element"""
        try:
            elem = element.find_element(By.CSS_SELECTOR, selector)
            logging.info(f"Found element for selector '{selector}': {elem.text.strip()}")
            return elem.text.strip()
        except NoSuchElementException:
            logging.warning(f"Element with selector '{selector}' not found")
            return ""

    def save_results(self, filename="acm_machine_learning_articles"):
        """Save results to both CSV and JSON files"""
        if not self.results:
            logging.warning("No results to save!")
            return

        df = pd.DataFrame(self.results)
        df.to_csv(f"{filename}.csv", index=False, encoding='utf-8')
        logging.info(f"Results saved to {filename}.csv")

        with open(f"{filename}.json", 'w', encoding='utf-8') as f:
            json.dump(self.results, f, ensure_ascii=False, indent=2)
        logging.info(f"Results saved to {filename}.json")

    def close(self):
        """Close the browser"""
        if self.driver:
            self.driver.quit()
            logging.info("Browser closed successfully")

def main():
    scraper = AcademicScraper()

    try:
        scraper.setup_driver()
        logging.info("Starting ACM scraping for Machine Learning articles...")
        scraper.scrape_acm(query="machine learning")  # Changed query to "machine learning"
        scraper.save_results("acm_machine_learning_articles")
    except Exception as e:
        logging.error(f"An error occurred in main: {e}")
    finally:
        scraper.close()

if __name__ == "__main__":
    main()


