"""Download works from ao3."""

import os
import traceback

import ao3downloader.exceptions as exceptions
import ao3downloader.strings as strings
import ao3downloader.text as text

from ao3downloader.fileio import FileOps
from ao3downloader.repo import Repository
from ao3downloader.soup import Soup


class Ao3:
    def __init__(self, repo: Repository, fileio: FileOps, soup: Soup, filetypes: list[str], images: bool, series: bool, pages: int):
        self.repo = repo
        self.fileio = fileio
        self.soup = soup
        
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
                series_soup = self.repo.get_soup(link)
                proceed_link = self.soup.proceed(series_soup)
                series_soup = self.repo.get_soup(proceed_link)
                work_urls = self.soup.get_work_urls(series_soup)
                for work_url in work_urls:
                    if work_url not in links_list:
                        links_list.append(work_url)
        elif strings.AO3_BASE_URL in link:
            while True:
                thesoup = self.repo.get_soup(link)
                urls = self.soup.get_work_and_series_urls(thesoup) if self.series else self.soup.get_work_urls(thesoup)
                if all(x in self.visited for x in urls): break
                for url in urls:
                    self.get_work_links_recursive(url, links_list)
                link = text.get_next_page(link)
                pagenum = text.get_page_number(link)
                if self.pages and pagenum == self.pages + 1: 
                    break
                else:
                    print('finished downloading page ' + str(pagenum - 1) + '. getting page ' + str(pagenum))
    
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
                thesoup = self.repo.get_soup(link)
                urls = soup.get_work_and_series_urls(thesoup)
                if all(x in self.visited for x in urls): break
                for url in urls:
                    self.download_recursive(url)
                link = soup.get_next_page(link)
                if self.pages and soup.get_page_number(link) == self.pages + 1: break
                self.fileio.write_log({'starting': link})
        else:
            raise exceptions.InvalidLinkException(strings.ERROR_INVALID_LINK)


    def download_series(self, link: str) -> None:
        """"Download all works in a series into a subfolder"""

        try:
            series_soup = self.repo.get_soup(link)
            proceed_link = self.soup.proceed(series_soup)
            series_soup = self.repo.get_soup(proceed_link)
            series_info = self.soup.get_series_info(series_soup)
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
            self.fileio.write_log(self.log)


    def try_download(self, work_url: str, chapters: str) -> str:
        """Main download logic"""

        thesoup = self.repo.get_soup(work_url)
        thesoup = self.soup.proceed(thesoup)

        if chapters is not None: # TODO this is a super awkward place for this logic to be and I don't like it.
            currentchapters = self.soup.get_current_chapters(thesoup)
            if currentchapters <= chapters:
                return False
        
        title = self.soup.get_title(thesoup)
        filename = self.fileio.get_valid_filename(title)

        for filetype in self.filetypes:
            link = self.soup.get_download_link(thesoup, filetype)
            response = self.repo.get_book(link)
            filetype = text.get_file_type(filetype)
            self.fileio.save_bytes(filename + filetype, response)

        if self.images:
            counter = 0
            imagelinks = self.soup.get_image_links(thesoup)
            for img in imagelinks:
                if str.startswith(img, '/'): break
                try:
                    ext = os.path.splitext(img)[1]
                    if '?' in ext: ext = ext[:ext.index('?')]
                    response = self.repo.get_book(img)
                    imagefile = filename + ' img' + str(counter).zfill(3) + ext
                    self.fileio.make_dir(strings.IMAGE_FOLDER_NAME)
                    self.fileio.save_bytes(os.path.join(strings.IMAGE_FOLDER_NAME, imagefile), response)
                    counter += 1
                except Exception as e:
                    self.fileio.write_log({
                        'message': strings.ERROR_IMAGE, 'link': work_url, 'title': title, 
                        'img': img, 'error': str(e), 'stacktrace': traceback.format_exc()})

        return title


    def log_error(self, exception: Exception):
        self.log['error'] = str(exception)
        self.log['success'] = False
        if not isinstance(exception, exceptions.Ao3DownloaderException):
            self.log['stacktrace'] = ''.join(traceback.TracebackException.from_exception(exception).format())
        self.fileio.write_log(self.log)
