from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from selenium.webdriver.common.keys import Keys
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
        # Add user agent to avoid detection
        options.add_argument(
            'user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')

        self.driver = webdriver.Chrome(options=options)
        self.wait = WebDriverWait(self.driver, 20)  # Increased timeout to 20 seconds

    def scrape_ieee(self, query="blockchain", num_pages=5):
        """
        Scrape IEEE Xplore Digital Library with tab management for detailed article views
        """
        try:
            # Encode query for URL
            encoded_query = quote(query)
            base_url = f"https://ieeexplore.ieee.org/search/searchresult.jsp?newsearch=true&queryText={encoded_query}&language=fr"
            logging.info(f"Accessing IEEE: {base_url}")

            self.driver.get(base_url)
            time.sleep(5)  # Wait for initial load

            # Store the main window handle
            main_window = self.driver.current_window_handle

            # Handle cookie banner
            try:
                cookie_button = self.wait.until(EC.element_to_be_clickable((By.ID, "onetrust-accept-btn-handler")))
                cookie_button.click()
                time.sleep(2)
            except:
                logging.info("No cookie banner found on IEEE")

            for page in range(num_pages):
                logging.info(f"Processing IEEE page {page + 1}")

                try:
                    # Wait for the search results container
                    results_container = self.wait.until(EC.presence_of_element_located(
                        (By.TAG_NAME, "xpl-results-list")))

                    # Get all article elements
                    articles = results_container.find_elements(By.CLASS_NAME, "List-results-items")

                    for article in articles:
                        try:
                            # Find the article title link and get its href
                            title_link = article.find_element(By.CSS_SELECTOR, ".fw-bold")
                            article_url = title_link.get_attribute("href")

                            # Open new tab with article URL
                            self.driver.execute_script(f"window.open('{article_url}', '_blank');")
                            time.sleep(2)

                            # Switch to the new tab
                            new_window = [window for window in self.driver.window_handles if window != main_window][-1]
                            self.driver.switch_to.window(new_window)

                            # Wait for article page to load
                            self.wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))
                            time.sleep(3)  # Allow dynamic content to load

                            # Extract detailed information from the article page
                            data = {
                                'journal': self._safe_get_text(self.driver, 'text-md-md-lh'),
                                'indexation': 'IEEE',
                                'publication': self._safe_get_text(self.driver,
                                                                   'text-base-md-lh.publisher-info-container.black-tooltip'),
                                'doi': self._safe_get_text(self.driver, 'u-pb-1.stats-document-abstract-doi'),
                                'titre': self._safe_get_text(self.driver, 'document-title.text-2xl-md-lh'),
                                'chercheurs': self._safe_get_text(self.driver, 'authors-info-container.overflow-ellipsis.text-base-md-lh.authors-minimized'),
                                'laboratoires': self._safe_get_text(self.driver, 'author-affiliations'),
                                'abstract': self.get_abstract(self.driver),
                                'keywords': self._safe_get_text(self.driver, 'doc-keywords-list.stats-keywords-list'),
                                'pays': self._extract_country(self.driver),
                                'quartile': self._get_quartile(self.driver)
                            }

                            self.results.append(data)
                            logging.info(f"Successfully extracted IEEE article: {data['titre'][:50]}...")

                            # Close the article tab and switch back to main window
                            self.driver.close()
                            self.driver.switch_to.window(main_window)
                            time.sleep(1)

                        except Exception as e:
                            logging.error(f"Error processing IEEE article: {e}")
                            # Make sure we return to main window if there's an error
                            if self.driver.current_window_handle != main_window:
                                self.driver.close()
                                self.driver.switch_to.window(main_window)
                            continue

                    # Handle pagination
                    try:
                        next_button = self.wait.until(EC.element_to_be_clickable(
                            (By.CLASS_NAME, "stats-Pagination_Next_11")))
                        if "disabled" in next_button.get_attribute("class"):
                            logging.info("Reached last page of IEEE results")
                            break
                        next_button.click()
                        time.sleep(3)
                    except:
                        logging.info("No more pages available on IEEE")
                        break

                except TimeoutException:
                    logging.error(f"Timeout on IEEE page {page + 1}")
                    break

        except Exception as e:
            logging.error(f"Error in IEEE scraping: {e}")

        finally:
            # Ensure we're on the main window before exiting
            if self.driver.current_window_handle != main_window:
                self.driver.switch_to.window(main_window)

    def scrape_sciencedirect(self, query="blockchain", num_pages=5):
        """
        Scrape ScienceDirect
        """
        try:
            encoded_query = quote(query)
            base_url = f"https://www.sciencedirect.com/search?qs={encoded_query}&language=fr"
            logging.info(f"Accessing ScienceDirect: {base_url}")

            self.driver.get(base_url)
            time.sleep(5)

            # Handle cookie consent if present
            try:
                cookie_button = self.wait.until(EC.element_to_be_clickable((By.ID, "onetrust-accept-btn-handler")))
                cookie_button.click()
                time.sleep(2)
            except:
                logging.info("No cookie banner found on ScienceDirect")

            for page in range(num_pages):
                logging.info(f"Processing ScienceDirect page {page + 1}")

                try:
                    # Wait for results to load
                    results = self.wait.until(EC.presence_of_all_elements_located(
                        (By.CLASS_NAME, "ResultItem")))

                    for article in results:
                        try:
                            # Expand article details if needed
                            try:
                                show_more = article.find_element(By.CLASS_NAME, "show-more-button")
                                show_more.click()
                                time.sleep(1)
                            except:
                                logging.debug("No show more button found")

                            data = {
                                'journal': self._safe_get_text(article, '.journal-name'),
                                'indexation': 'ScienceDirect',
                                'publication': self._safe_get_text(article, '.publication-year'),
                                'doi': self._safe_get_text(article, '.doi-link'),
                                'titre': self._safe_get_text(article, '.result-title'),
                                'chercheurs': self._safe_get_text(article, '.author-list'),
                                'laboratoires': self._safe_get_text(article, '.institution'),
                                'abstract': self._safe_get_text(article, '.abstract-text'),
                                'keywords': self._safe_get_text(article, '.keywords'),
                                'pays': self._extract_country(article),
                                'quartile': self._get_quartile(article)
                            }
                            self.results.append(data)
                            logging.info(f"Successfully extracted ScienceDirect article: {data['titre'][:50]}...")

                        except Exception as e:
                            logging.error(f"Error processing ScienceDirect article: {e}")
                            continue

                    # Handle pagination
                    try:
                        next_button = self.wait.until(EC.element_to_be_clickable(
                            (By.CSS_SELECTOR, "[data-testid='pagination-next-button']")))
                        if "disabled" in next_button.get_attribute("class"):
                            logging.info("Reached last page of ScienceDirect results")
                            break
                        next_button.click()
                        time.sleep(3)
                    except:
                        logging.info("No more pages available on ScienceDirect")
                        break

                except TimeoutException:
                    logging.error(f"Timeout on ScienceDirect page {page + 1}")
                    break

        except Exception as e:
            logging.error(f"Error in ScienceDirect scraping: {e}")

    def scrape_acm(self, query="blockchain", num_pages=5):
        """
        Scrape ACM Digital Library
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
                                'journal': self._safe_get_text(article, '.epub-section__title'),
                                'indexation': 'ACM',
                                'publication': self._safe_get_text(article, '.bookPubDate'),
                                'doi': self._safe_get_text(article, '.issue-item__doi'),
                                'titre': self._safe_get_text(article, '.issue-item__title'),
                                'chercheurs': self._safe_get_text(article, '.author-names'),
                                'laboratoires': self._safe_get_text(article, '.author-info__body'),
                                'abstract': self._safe_get_text(article, '.abstractInFull'),
                                'keywords': self._safe_get_text(article, '.keywords__content'),
                                'pays': self._extract_country(article),
                                'quartile': self._get_quartile(article)
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

    def get_abstract(self, driver):
        try:
            # Wait for the abstract element to be present
            abstract_element = self.wait.until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "div[xplmathjax]"))
            )
            return abstract_element.text.strip()
        except TimeoutException:
            logging.error("Timeout waiting for abstract element")
            return ""
        except Exception as e:
            logging.error(f"Error extracting abstract: {e}")
            return ""

    def _safe_get_text(self, element, selector):
        """Safely extract text from an element"""
        try:
            elem = element.find_element(By.CLASS_NAME, selector)
            return elem.text.strip()
        except NoSuchElementException:
            return ""

    def _extract_country(self, article):
        """Extract country from affiliation information"""
        try:
            affiliation = self._safe_get_text(article, '.author-info__body')
            # Add more sophisticated country extraction logic here
            return ""
        except:
            return ""

    def _get_quartile(self, article):
        """Get journal quartile"""
        # Implement journal quartile logic here
        return ""

    def save_results(self, filename="results"):
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

        logging.info("Starting IEEE scraping...")
        scraper.scrape_ieee(query="AI")

        scraper.save_results("ai_articles")

    except Exception as e:
        logging.error(f"An error occurred in main: {e}")

    finally:
        scraper.close()


if __name__ == "__main__":
    main()