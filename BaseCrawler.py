"""
BaseCrawler - Abstract base class for web crawling using Selenium with headless Chromium.

This module provides a base class for implementing web crawlers that use Selenium
to interact with web pages in a headless Chrome browser.
"""

from abc import ABC, abstractmethod
from typing import Optional
import logging
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import WebDriverException, TimeoutException


class BaseCrawler(ABC):
    """
    Abstract base class for web crawling using Selenium with headless Chromium.

    This class provides the basic infrastructure for crawling web pages using
    Selenium WebDriver with a headless Chrome browser. Derived classes must
    implement the `manage()` method to define how to process the crawled content.

    Attributes:
        driver (webdriver.Chrome): The Selenium WebDriver instance
        wait (WebDriverWait): WebDriverWait instance for explicit waits
        logger (logging.Logger): Logger instance for the crawler
    """

    def __init__(
        self,
        headless: bool = True,
        timeout: int = 10,
        window_size: str = "1920,1080",
        user_agent: Optional[str] = None,
        disable_images: bool = False,
        log_level: int = logging.INFO
    ):
        """
        Initialize the BaseCrawler with Selenium WebDriver.

        Args:
            headless (bool): Run browser in headless mode. Default is True.
            timeout (int): Default timeout for page loads in seconds. Default is 10.
            window_size (str): Browser window size as "width,height". Default is "1920,1080".
            user_agent (str, optional): Custom user agent string. Default is None.
            disable_images (bool): Disable image loading for faster crawling. Default is False.
            log_level (int): Logging level. Default is logging.INFO.
        """
        self.logger = self._setup_logger(log_level)
        self.timeout = timeout
        self.driver = self._initialize_driver(
            headless=headless,
            window_size=window_size,
            user_agent=user_agent,
            disable_images=disable_images
        )
        self.wait = WebDriverWait(self.driver, timeout)
        self.logger.info("BaseCrawler initialized successfully")

    def _setup_logger(self, log_level: int) -> logging.Logger:
        """
        Set up logger for the crawler.

        Args:
            log_level (int): Logging level

        Returns:
            logging.Logger: Configured logger instance
        """
        logger = logging.getLogger(self.__class__.__name__)
        logger.setLevel(log_level)

        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                '{ "time":"%(asctime)s", "class":"%(name)s", "level":"%(levelname)s", "message":"%(message)s" }'
            )
            handler.setFormatter(formatter)
            logger.addHandler(handler)

        return logger

    def _initialize_driver(
        self,
        headless: bool,
        window_size: str,
        user_agent: Optional[str],
        disable_images: bool
    ) -> webdriver.Chrome:
        """
        Initialize and configure the Chrome WebDriver.

        Args:
            headless (bool): Run browser in headless mode
            window_size (str): Browser window size
            user_agent (str, optional): Custom user agent string
            disable_images (bool): Disable image loading

        Returns:
            webdriver.Chrome: Configured Chrome WebDriver instance

        Raises:
            WebDriverException: If driver initialization fails
        """
        chrome_options = Options()

        # Headless mode
        if headless:
            chrome_options.add_argument('--headless=new')

        # Basic options for stability and performance
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--disable-gpu')
        chrome_options.add_argument(f'--window-size={window_size}')
        chrome_options.add_argument('--disable-blink-features=AutomationControlled')

        # Custom user agent
        if user_agent:
            chrome_options.add_argument(f'user-agent={user_agent}')

        # Disable images for faster loading
        if disable_images:
            prefs = {"profile.managed_default_content_settings.images": 2}
            chrome_options.add_experimental_option("prefs", prefs)

        # Additional options to avoid detection
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option('useAutomationExtension', False)

        try:
            driver = webdriver.Chrome(options=chrome_options)
            driver.execute_cdp_cmd('Network.setUserAgentOverride', {
                "userAgent": driver.execute_script("return navigator.userAgent").replace('Headless', '')
            })
            self.logger.info("Chrome WebDriver initialized successfully")
            return driver
        except WebDriverException as e:
            self.logger.error(f"Failed to initialize Chrome WebDriver: {e}")
            raise

    def crawl(self, url: str) -> None:
        """
        Crawl the specified URL and call the manage method.

        This method navigates to the given URL, waits for the page to load,
        and then calls the abstract manage() method that must be implemented
        by derived classes.

        Args:
            url (str): The URL to crawl

        Raises:
            TimeoutException: If page load times out
            WebDriverException: If navigation fails
        """
        try:
            self.logger.info(f"Crawling URL: {url}")
            self.driver.get(url)

            # Wait for page to be ready
            self.wait.until(
                lambda driver: driver.execute_script("return document.readyState") == "complete"
            )

            self.logger.info(f"Page loaded successfully: {url}")

            # Call the abstract manage method
            self.manage()

        except TimeoutException as e:
            self.logger.error(f"Timeout while loading {url}: {e}")
            raise
        except WebDriverException as e:
            self.logger.error(f"WebDriver error while crawling {url}: {e}")
            raise
        except Exception as e:
            self.logger.error(f"Unexpected error while crawling {url}: {e}")
            raise

    @abstractmethod
    def manage(self) -> None:
        """
        Abstract method to manage/process the crawled page content.

        This method must be implemented by derived classes to define how
        to interact with and extract data from the crawled page.

        The method has access to:
        - self.driver: The Selenium WebDriver instance
        - self.wait: WebDriverWait instance for explicit waits
        - self.logger: Logger instance

        Example implementation in derived class:
            def manage(self):
                title = self.driver.title
                content = self.driver.find_element(By.TAG_NAME, "body").text
                self.logger.info(f"Page title: {title}")
                # Process content as needed
        """
        pass

    def get_page_source(self) -> str:
        """
        Get the current page source HTML.

        Returns:
            str: The page source HTML
        """
        return self.driver.page_source

    def get_current_url(self) -> str:
        """
        Get the current URL.

        Returns:
            str: The current URL
        """
        return self.driver.current_url

    def take_screenshot(self, filepath: str) -> bool:
        """
        Take a screenshot of the current page.

        Args:
            filepath (str): Path where to save the screenshot

        Returns:
            bool: True if screenshot was saved successfully, False otherwise
        """
        try:
            self.driver.save_screenshot(filepath)
            self.logger.info(f"Screenshot saved to: {filepath}")
            return True
        except Exception as e:
            self.logger.error(f"Failed to save screenshot: {e}")
            return False

    def close(self) -> None:
        """
        Close the browser and clean up resources.
        """
        if self.driver:
            try:
                self.driver.quit()
                self.logger.info("WebDriver closed successfully")
            except Exception as e:
                self.logger.error(f"Error closing WebDriver: {e}")

    def __enter__(self):
        """
        Context manager entry.

        Returns:
            BaseCrawler: Self instance
        """
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """
        Context manager exit - ensures driver is closed.

        Args:
            exc_type: Exception type
            exc_val: Exception value
            exc_tb: Exception traceback
        """
        self.close()

    def __del__(self):
        """
        Destructor - ensures driver is closed when object is garbage collected.
        """
        self.close()
