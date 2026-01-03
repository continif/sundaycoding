from BaseCrawler import BaseCrawler
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC

# Struttura: https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/User-Agent/Firefox
# //*[@id="main-content"]/ol[class="c-release-list"]/li/ol/li/a
# Esempi:
# Windows 10/11	Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:146.0) Gecko/20100101 Firefox/146.0
# macOS (Intel/M1/M2)	Mozilla/5.0 (Macintosh; Intel Mac OS X 15.7; rv:146.0) Gecko/20100101 Firefox/146.0
# Linux (x64)	Mozilla/5.0 (X11; Linux x86_64; rv:146.0) Gecko/20100101 Firefox/146.0
# Linux (Ubuntu)	Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:146.0) Gecko/20100101 Firefox/146.0
# Android (Smartphone)	Mozilla/5.0 (Android 15; Mobile; rv:146.0) Gecko/146.0 Firefox/146.0
# Android (Tablet)	Mozilla/5.0 (Android 15; Tablet; rv:146.0) Gecko/146.0 Firefox/146.0

class FirefoxUserAgentsCrawler(BaseCrawler):
    """
    Crawler that extracts Firefox user agents from a specific web page.
    """

    def __init__(self, **kwargs):
        """
        Initialize the FirefoxUserAgentsCrawler.

        Args:
            **kwargs: Arguments to pass to BaseCrawler
        """
        super().__init__(**kwargs)
        if not kwargs.get('start_url'):
            self.start_url = "https://www.firefox.com/en-US/releases/"
        if not kwargs.get('headless'):
            self.headless = True
        self.platforms = [
            "Windows NT 10.0; Win64; x64",
            "Macintosh; Intel Mac OS X 15.7",
            "X11; Linux x86_64",
            "X11; Ubuntu; Linux x86_64",
            "Android 15; Mobile",
            "Android 15; Tablet"
        ]
        self.geko_date='20100101'
        self.geko_versions = {'Android':'{FIREFOX_VERSION}', 'default':self.geko_date}
        self.xpath = '//*[@id="main-content"]/ol[@class="c-release-list"]/li/ol/li/a'
        self.base_user_agent = "Mozilla/5.0 ({PLATFORM}; rv:{GEKO_VERSION}) Gecko/{GEKO_DATE} Firefox/{FIREFOX_VERSION}"
        self.user_agents = []

    def manage(self) -> None:
        """
        Extract Firefox user agents from the page.
        """
        try:
            # Wait for the main content to load
            self.wait.until(EC.presence_of_element_located((By.ID, "main-content")))

            # Locate user agent elements
            user_agent_elements = self.driver.find_elements(
                By.XPATH,
                self.xpath
            )
            versions=[elem.text for elem in user_agent_elements]
            self.logger.info(f"Found {len(versions)} Firefox versions")

            # Extract and store user agents
            for temp_platform in self.platforms:
                Geko_Version = self.geko_versions['default']
                if temp_platform.startswith("Android"):
                    Geko_Version = versions[self.platforms.index(temp_platform)]
                for version in versions:
                    maj_ver=version.split('.')[0]
                    if maj_ver.isdigit() and int(maj_ver)>139:
                            self.user_agents.append(
                                self.base_user_agent.format(
                                    PLATFORM=temp_platform,
                                    GEKO_VERSION=Geko_Version,
                                    GEKO_DATE=self.geko_date,
                                    FIREFOX_VERSION=version
                                )
                            )





            self.logger.info(f"Extracted {len(self.user_agents)} Firefox user agents")

        except Exception as e:
            self.logger.error(f"Error in manage method: {e}")
            raise

    def get_user_agents(self) -> list:
        """
        Get the extracted Firefox user agents.

        Returns:
            list: List of extracted user agent strings
        """
        return self.user_agents


if __name__ == "__main__":
    crawler = FirefoxUserAgentsCrawler()
    crawler.crawl(crawler.start_url)
    user_agents = crawler.get_user_agents()
    for ua in user_agents:
        print(ua)
