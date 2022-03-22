"""Download works from ao3."""

import os
import requests
import traceback

import ao3downloader.exceptions as exceptions
import ao3downloader.fileio as fileio
import ao3downloader.repo as repo
import ao3downloader.soup as soup
import ao3downloader.strings as strings

from bs4 import BeautifulSoup


class Ao3:
    def __init__(self, session: requests.sessions.Session, logfile: str, folder: str, filetypes: list[str], images: bool, series: bool, pages: int):
        self.session = session
        self.logfile = logfile
        self.folder = folder
        self.filetypes = filetypes
        self.images = images
        self.series = series
        self.pages = pages
        self.visited = []
        self.log = {}


    def download(self, link: str) -> None:
        try:
            self.download_recursive(link)
        except Exception as e:
            self.log_error(e)


    def update(self, link: str, chapters: str,) -> None:
        try:
            self.download_work(link, chapters)
        except Exception as e:
            self.log_error(e)


    def update_series(self, link: str, existing: list[str]) -> None:
        try:
            self.visited.extend(existing)
            self.download_series(link)
        except Exception as e:
            self.log_error(e)


    def get_work_links(self, link: str) -> list[str]:
        links_list = []
        self.get_work_links_recursive(link, links_list)
        return links_list


    def get_work_links_recursive(self, link: str, links_list: list[str]) -> None:

        if link in self.visited: return
        self.visited.append(link)

        if '/works/' in link:
            if link not in links_list:
                links_list.append(link)
        elif '/series/' in link:
            if self.series:
                series_soup = repo.get_soup(link, self.session)
                series_soup = self.proceed(series_soup)
                work_urls = soup.get_work_urls(series_soup)
                for work_url in work_urls:
                    if work_url not in links_list:
                        links_list.append(work_url)
        elif strings.AO3_BASE_URL in link:
            while True:
                thesoup = repo.get_soup(link, self.session)
                urls = soup.get_work_and_series_urls(thesoup) if self.series else soup.get_work_urls(thesoup)
                if all(x in self.visited for x in urls): break
                for url in urls:
                    self.get_work_links_recursive(url, links_list)
                link = soup.get_next_page(link)
                if self.pages and soup.get_page_number(link) == self.pages + 1: break


    def download_recursive(self, link: str) -> None:

        if link in self.visited: return
        self.visited.append(link)

        if '/series/' in link:
            if self.series:
                self.log = {}
                self.download_series(link)
        elif '/works/' in link:
            self.log = {}
            self.download_work(link, None)
        elif strings.AO3_BASE_URL in link:
            while True:
                thesoup = repo.get_soup(link, self.session)
                urls = soup.get_work_and_series_urls(thesoup)
                if all(x in self.visited for x in urls): break
                for url in urls:
                    self.download_recursive(url)
                link = soup.get_next_page(link)
                if self.pages and soup.get_page_number(link) == self.pages + 1: break
                fileio.write_log(self.logfile, {'starting': link})
        else:
            raise exceptions.InvalidLinkException(strings.ERROR_INVALID_LINK)


    def download_series(self, link: str) -> None:
        """"Download all works in a series into a subfolder"""

        try:
            series_soup = repo.get_soup(link, self.session)
            series_soup = self.proceed(series_soup, self.session)
            series_info = soup.get_series_info(series_soup)
            series_title = series_info['title']
            self.log['series'] = series_title
            for work_url in series_info['work_urls']:
                if work_url not in self.visited:
                    self.visited.append(work_url)
                    self.download_work(work_url, None)
        except Exception as e:
            self.log['link'] = link
            self.log_error(e)


    def download_work(self, link: str, chapters: str) -> None:
        """Download a single work"""

        try:
            self.log['link'] = link
            title = self.try_download(link, chapters)
            if title == False: return
            self.log['title'] = title
        except Exception as e:
            self.log_error(e)
        else:
            self.log['success'] = True
            fileio.write_log(self.logfile, self.log)


    def try_download(self, work_url: str, chapters: str) -> str:
        """Main download logic"""

        thesoup = repo.get_soup(work_url, self.session)
        thesoup = self.proceed(thesoup)

        if chapters is not None: # TODO this is a super awkward place for this logic to be and I don't like it.
            currentchapters = soup.get_current_chapters(thesoup)
            if currentchapters <= chapters:
                return False
        
        title = soup.get_title(thesoup)
        filename = fileio.get_valid_filename(title)

        for filetype in self.filetypes:
            link = soup.get_download_link(thesoup, filetype)
            response = repo.get_book(link, self.session)
            filetype = self.get_file_type(filetype)
            fileio.save_bytes(self.folder, filename + filetype, response)

        if self.images:
            counter = 0
            imagelinks = soup.get_image_links(thesoup)
            for img in imagelinks:
                if str.startswith(img, '/'): break
                try:
                    ext = os.path.splitext(img)[1]
                    if '?' in ext: ext = ext[:ext.index('?')]
                    response = repo.get_book(img, self.session)
                    imagefile = filename + ' img' + str(counter).zfill(3) + ext
                    imagefolder = os.path.join(self.folder, strings.IMAGE_FOLDER_NAME)
                    fileio.make_dir(imagefolder)
                    fileio.save_bytes(imagefolder, imagefile, response)
                    counter += 1
                except Exception as e:
                    fileio.write_log(self.logfile, {
                        'message': strings.ERROR_IMAGE, 'link': work_url, 'title': title, 
                        'img': img, 'error': str(e), 'stacktrace': traceback.format_exc()})

        return title


    def proceed(self, thesoup: BeautifulSoup) -> BeautifulSoup:
        """Check locked/deleted and proceed through explicit agreement if needed"""

        if soup.is_locked(thesoup):
            raise exceptions.LockedException(strings.ERROR_LOCKED)
        if soup.is_deleted(thesoup):
            raise exceptions.DeletedException(strings.ERROR_DELETED)
        if soup.is_explicit(thesoup):
            proceed_url = soup.get_proceed_link(thesoup)
            thesoup = repo.get_soup(proceed_url, self.session)
        return thesoup


    def get_file_type(filetype: str) -> str:
        return '.' + filetype.lower()


    def log_error(self, exception: Exception):
        self.log['error'] = str(exception)
        self.log['success'] = False
        if not isinstance(exception, exceptions.Ao3DownloaderException):
            self.log['stacktrace'] = ''.join(traceback.TracebackException.from_exception(exception).format())
        fileio.write_log(self.logfile, self.log)
