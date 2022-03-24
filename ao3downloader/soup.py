"""Logic for navigating BeautifulSoup output"""

import re

from bs4 import BeautifulSoup

import ao3downloader.exceptions as exceptions
import ao3downloader.strings as strings
import ao3downloader.text as textparse


class Soup:

    def get_token(self, soup: BeautifulSoup) -> str:
        """Get authentication token for logging in to ao3."""

        token = (soup.find('form', class_='new_user')
                    .find('input', attrs={'name': 'authenticity_token'})
                    .get('value'))
        return token


    def get_image_links(self, soup: BeautifulSoup) -> list[str]:
        links = []
        work = soup.find('div', id='workskin')
        if not work: return links
        images = work.find_all('img')
        for img in images:
            href = img.get('src')
            if href:
                links.append(href)
        return links


    def get_series_info(self, soup: BeautifulSoup) -> dict:
        """Get series title and list of work urls."""

        work_urls = self.get_work_urls(soup)

        # create dictionary for series info
        series_info = {'work_urls': work_urls}

        # add series title to dictionary
        series_info['title'] = self.get_title(soup)

        return series_info


    def get_work_urls(self, soup: BeautifulSoup) -> list[str]:
        """Get all links to ao3 works on a page"""

        # work urls can be identified by the prefix /works/ followed by only digits
        pattern = r'\/works\/\d+$'
        expression = re.compile(pattern)

        work_urls = []

        # get links to all works on the page
        all_links = soup.find_all('a')
        for link in all_links:
            href = link.get('href')
            if href and expression.match(href):
                url = strings.AO3_BASE_URL + href
                work_urls.append(url)

        return work_urls


    def get_work_and_series_urls(self, soup: BeautifulSoup) -> list[str]:
        """Get all links to ao3 works or series on a page"""

        # work urls can be identified by the prefix /works/ followed by only digits
        workpattern = r'\/works\/\d+$'
        workexpression = re.compile(workpattern)

        # series urls can be identified in the same manner
        seriespattern = r'\/series\/\d+$'
        seriesexpression = re.compile(seriespattern)

        urls = []

        # get links to all works on the page
        all_links = soup.find_all('a')
        for link in all_links:
            href = link.get('href')
            if href and (workexpression.match(href) or seriesexpression.match(href)):
                url = strings.AO3_BASE_URL + href
                urls.append(url)

        return urls


    def proceed(self, thesoup: BeautifulSoup) -> str:
        """Check locked/deleted and proceed through explicit agreement if needed"""

        if self.is_locked(thesoup):
            raise exceptions.LockedException(strings.ERROR_LOCKED)
        if self.is_deleted(thesoup):
            raise exceptions.DeletedException(strings.ERROR_DELETED)
        if self.is_explicit(thesoup):
            proceed_url = self.get_proceed_link(thesoup)
        return proceed_url


    def get_proceed_link(self, soup: BeautifulSoup) -> str:
        """Get link to proceed through explict work agreement."""

        try:
            link = (soup.find('div', class_='works-show region')
                        .find('ul', class_='actions')
                        .find('li')
                        .find('a', text=strings.AO3_PROCEED)
                        .get('href'))
        except AttributeError as e:
            raise exceptions.ProceedException(strings.ERROR_PROCEED_LINK) from e
        return strings.AO3_BASE_URL + link


    def get_download_link(self, soup: BeautifulSoup, download_type: str) -> str:
        """Get download link from ao3 work page."""

        try:
            link = (soup.find('li', class_='download')
                        .find('a', text=download_type)
                        .get('href'))
        except AttributeError as e:
            raise exceptions.DownloadException(strings.ERROR_DOWNLOAD_LINK) from e
        return strings.AO3_BASE_URL + link


    def get_title(self, soup: BeautifulSoup) -> str:
        """Get title of ao3 work, stripping out extraneous information."""

        return (soup.title.get_text().strip()
                .replace(strings.AO3_TITLE, '')
                .replace(strings.AO3_CHAPTER_TITLE, ''))


    def get_current_chapters(self, soup: BeautifulSoup) -> str:
        text = (soup.find('dl', class_='stats')
                    .find('dd', class_='chapters')
                    .get_text().strip())

        index = text.find('/')
        if index == -1: return -1

        return textparse.get_current_chapters(text, index)
        

    def is_locked(self, soup: BeautifulSoup) -> bool:
        return self.string_exists(soup, strings.AO3_LOCKED)


    def is_deleted(self, soup: BeautifulSoup) -> bool:
        return self.string_exists(soup, strings.AO3_DELETED)


    def is_explicit(self, soup: BeautifulSoup) -> bool:
        return self.string_exists(soup, strings.AO3_EXPLICIT)


    def is_failed_login(self, soup: BeautifulSoup) -> bool:
        return self.string_exists(soup, strings.AO3_FAILED_LOGIN)


    def string_exists(self, soup: BeautifulSoup, string: str) -> bool:
        pattern = string
        expression = re.compile(pattern)
        match = soup.find_all(text=expression)
        return len(match) > 0
