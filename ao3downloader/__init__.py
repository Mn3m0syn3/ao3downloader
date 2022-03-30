import datetime
import ebooklib
import itertools
import json
import mobi
import os
import re
import requests
import pdfquery
import traceback
import shutil

from bs4 import BeautifulSoup
from ebooklib import epub
from requests import codes
from time import sleep
from tqdm import tqdm

import xml.etree.ElementTree as ET
import ao3downloader.strings as strings


class Ao3DownloaderException(Exception):
    pass

class LockedException(Ao3DownloaderException):
    pass

class DeletedException(Ao3DownloaderException):
    pass

class ProceedException(Ao3DownloaderException):
    pass

class DownloadException(Ao3DownloaderException):
    pass

class InvalidLinkException(Ao3DownloaderException):
    pass

class LoginException(Ao3DownloaderException):
    pass

class SeriesInfo:
    def __init__(self, title: str, works: list[str]):
        self.title = title
        self.works = works

class FicFileInfo:
    def __init__(self, link: str, stats: str, series: list[str]):
        self.link = link
        self.stats = stats
        self.series = series

class TextParse:
    INVALID_FILENAME_CHARACTERS = '<>:"/\|?*.' + ''.join(chr(i) for i in range(32))

    def get_valid_filename(self, filename: str) -> str:
        valid_name = filename.translate({ord(i):None for i in self.INVALID_FILENAME_CHARACTERS})
        return valid_name[:100].strip()

    def get_file_type(self, filetype: str) -> str:
        return '.' + filetype.lower()

    def get_next_page(self, link: str) -> str:
        index = str.find(link, 'page=')
        if index == -1:
            if str.find(link, '?') == -1:
                newlink = link + '?page=2'
            else:
                newlink = link + '&page=2'
        else:
            i = index + 5
            page = self.get_num_from_link(link, i)
            nextpage = int(page) + 1
            newlink = link.replace('page=' + page, 'page=' + str(nextpage))
        return newlink

    def get_page_number(self, link: str) -> int:
        index = str.find(link, 'page=')
        if index == -1:
            return 1
        else:
            i = index + 5
            page = self.get_num_from_link(link, i)
            return int(page)

    def get_num_from_link(self, link: str, index: int) -> str:
        end = index + 1
        while end < len(link) and str.isdigit(link[index:end+1]):
            end = end + 1
        return link[index:end]

    def get_total_chapters(self, text: str, index: int) -> str:
        '''read characters after index until encountering a space.'''
        totalchap = ''
        for c in text[index+1:]:
            if c.isspace():
                break
            else:
                totalchap += c
        return totalchap

    def get_current_chapters(self, text: str, index: int) -> str:
        ''' 
        reverse text before index, then read characters from beginning of reversed text 
        until encountering a space, then un-reverse the value you got. 
        we assume here that the text does not include unicode values.
        this should be safe because ao3 doesn't have localization... I think.
        '''
        currentchap = ''
        for c in reversed(text[:index]):
            if c.isspace():
                break
            else:
                currentchap += c
        currentchap = currentchap[::-1]
        return currentchap

    def get_payload(self, username, password, token):
        """Get payload for ao3 login."""

        payload = {
            'user[login]': username,
            'user[password]': password,
            'user[remember_me]': '1',
            'utf8': '&#x2713;',
            'authenticity_token': token
        }
        return payload

    def get_title_dict(self, logs: list[dict]) -> dict[str, str]:
        dictionary = {}
        titles = filter(lambda x: 'title' in x and 'link' in x, logs)
        for obj in list(titles):
            link = obj['link']
            if link not in dictionary:
                title = obj['title']
                dictionary[link] = title
        return dictionary

    def get_unsuccessful_downloads(self, logs: list[dict]) -> list[str]:
        links = []
        errors = filter(lambda x:'link' in x and 'success' in x and x['success'] == False, logs)
        for error in errors:
            link = error['link']
            if link not in links: 
                links.append(link)
        return links

class SoupParse:
    def __init__(self, textparse: TextParse):
        self.textparse = textparse

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

    def get_series_info(self, soup: BeautifulSoup) -> SeriesInfo:
        """Get series title and list of work urls."""

        title = self.get_title(soup)
        work_urls = self.get_work_urls(soup)
        return SeriesInfo(title, work_urls)

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
            raise LockedException(strings.ERROR_LOCKED)
        if self.is_deleted(thesoup):
            raise DeletedException(strings.ERROR_DELETED)
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
            raise ProceedException(strings.ERROR_PROCEED_LINK) from e
        return strings.AO3_BASE_URL + link

    def get_download_link(self, soup: BeautifulSoup, download_type: str) -> str:
        """Get download link from ao3 work page."""

        try:
            link = (soup.find('li', class_='download')
                        .find('a', text=download_type)
                        .get('href'))
        except AttributeError as e:
            raise DownloadException(strings.ERROR_DOWNLOAD_LINK) from e
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

        return self.textparse.get_current_chapters(text, index)
        
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

    def get_work_link_html(soup: BeautifulSoup) -> str:
        msg = soup.select('#preface .message a')
        if msg and len(msg) == 2: # there should be exactly two links in here
            return msg[1].get('href') # we want the second one
        return None

    def get_stats_html(soup: BeautifulSoup) -> str:
        stats = soup.select('#preface .meta .tags dd')
        for dd in stats:
            if 'Chapters: ' in dd.text:
                return dd.text
        return None

    def get_series_html(soup: BeautifulSoup) -> list[str]:
        series = []
        links = soup.select('#preface .meta .tags dd a')
        for link in links:
            href = link.get('href')
            if href and strings.AO3_IDENTIFIER_SERIES in href:
                series.append(href)
        return series

    def get_work_link_mobi(soup: BeautifulSoup) -> str:
        # it's ok if there are other work links in the file, because the relevant one will always be the first to appear
        # can't use a more specific selector because the html that comes out of the mobi parser is poorly formatted rip me
        link = soup.find('a', href=lambda x: x and strings.AO3_IDENTIFIER_WORK in x)
        if link: return link.get('href')
        return None

    def get_stats_mobi(soup: BeautifulSoup) -> str:
        stats = soup.find('blockquote', string=lambda x: x and 'Chapters: ' in x)
        if stats: return stats.text
        return None

    def get_series_mobi(soup: BeautifulSoup) -> list[str]:
        series = []
        tag = soup.find('p', string=lambda x: x and x == 'Series:')
        if tag:
            block = tag.find_next_sibling('blockquote')
            if block:
                links = block.find_all('a', href=lambda x: x and strings.AO3_IDENTIFIER_SERIES in x)
                for link in links:
                    series.append(link.get('href'))
        return series

class XmlParse:
    def get_work_link_epub(xml: ET.Element) -> str:
        # assumption: the xml does not contain any links to other works than the one we are interested in. 
        # since this file should not include user-generated html (such as summary) this should be safe.
        # that's a lot of shoulds but we'll let it go because I said so.
        for a in xml.iter('{http://www.w3.org/1999/xhtml}a'):
            href = a.get('href')
            if href and strings.AO3_IDENTIFIER_WORK in href:
                return href
        return None

    def get_stats_epub(xml: ET.Element) -> str:
        # ao3 stores chapter stats in a dd tag with class 'calibre5' for whatever reason.
        for dd in xml.iter('{http://www.w3.org/1999/xhtml}dd'):
            cls = dd.get('class')
            if cls and 'calibre5' in cls:
                return dd.text
        return None

    def get_series_epub(xml: ET.Element) -> list[str]:
        series = []
        for a in xml.iter('{http://www.w3.org/1999/xhtml}a'):
            href = a.get('href')
            if href and strings.AO3_IDENTIFIER_SERIES in href:
                series.append(href)
        return series

class PdfParse:
    def get_work_link_pdf(pdf: pdfquery.PDFQuery) -> str:
        # assumption: work link is on the same line as preceding text. probably fine. ¯\_(ツ)_/¯
        # doing some weird string parsing here. considered taking a similar approach to the epub function
        # and parsing the xml tree for URIs. however that might break if someone linked another work in their summary.
        linktext = pdf.pq('LTTextLineHorizontal:contains("Posted originally on the Archive of Our Own at ")').text()
        workindex = linktext.find('/works/')
        endindex = linktext[workindex:].find('.')
        worknumber = linktext[workindex:workindex+endindex]
        if worknumber: return strings.AO3_BASE_URL + worknumber
        return None

    def get_stats_pdf(pdf: pdfquery.PDFQuery) -> str:
        # assumption: chapter count is on same line as 'Chapters: '. reasonably safe because the 
        # preceding metadata is always going to be no longer than 'Published: yyyy-MM-dd Updated: yyyy-MM-dd '.
        # if someone puts 'Chapters: ' in their summary for some fool reason... I don't know, it might still work.
        return pdf.pq('LTTextLineHorizontal:contains("Chapters: ")').text()

    def get_series_pdf(pdf: pdfquery.PDFQuery) -> list[str]:
        links = map(lambda x: x.attrib['URI'] if 'URI' in x.attrib else '', pdf.pq('Annot'))
        series = filter(lambda x: strings.AO3_IDENTIFIER_SERIES in x, links)
        return list(series)

class FileOps:
    def __init__(self):
        self.folder = strings.DOWNLOAD_FOLDER_NAME
        if not os.path.exists(self.folder): os.mkdir(self.folder)
        if not os.path.exists(strings.LOG_FOLDER_NAME): os.mkdir(strings.LOG_FOLDER_NAME)
        self.logfile = os.path.join(strings.LOG_FOLDER_NAME, strings.LOG_FILE_NAME)
        self.settingsfile = strings.SETTINGS_FILE_NAME

    def make_dir(self, folder: str):
        folder = os.path.join(self.folder, folder)
        if not os.path.exists(folder): os.mkdir(folder)

    def write_log(self, log: dict) -> None:
        log['timestamp'] = datetime.datetime.now().strftime('%m/%d/%Y, %H:%M:%S')
        with open(self.logfile, 'a', encoding='utf-8') as f:
            json.dump(log, f, ensure_ascii=False)
            f.write('\n')

    def save_bytes(self, filename: str, content: bytes) -> None:
        file = os.path.join(self.folder, filename)
        with open(file, 'wb') as f:
            f.write(content)

    def save_setting(self, setting: str, value) -> None:
        js = self.get_settings()
        if value is None:
            js.pop(setting, None)
        else:
            js[setting] = value
        with open(self.settingsfile, 'w') as f:
            f.write(json.dumps(js))

    def get_setting(self, setting: str):
        js = self.get_settings()
        try:
            return js[setting]
        except:
            return ''

    def get_settings(self) -> dict:
        with open(self.settingsfile, 'a', encoding='utf-8'):
            pass
        with open(self.settingsfile, 'r', encoding='utf-8') as f:
            try:
                return json.load(f)
            except:
                return {}

    def setting(self, prompt: str, setting: str):
        value = self.get_setting(setting)
        if value == '':
            print(prompt)
            value = input()
            self.save_setting(setting, value)
        return value

    def load_logfile(self) -> list[dict]:
        logs = []
        try:
            with open(self.logfile, 'r', encoding='utf-8') as f:
                objects = map(lambda x: json.loads(x), f.readlines())
                logs.extend(list(objects))
        except FileNotFoundError:
            pass
        return logs

    def file_exists(self, id: str, titles: dict[str, str], filetypes: list[str]) -> bool:
        if id not in titles: return False
        filename = self.textparse.get_valid_filename(titles[id])
        files = list(map(lambda x: os.path.join(self.folder, filename + '.' + x.lower()), filetypes))
        for file in files:
            if not os.path.exists(file):
                return False
        return True

    def get_files_of_type(self, folder: str, filetypes: list[str]) -> list[dict[str, str]]:
        results = []
        for subdir, dirs, files in os.walk(folder):
            for file in files:
                filetype = os.path.splitext(file)[1].upper()[1:]
                if filetype in filetypes:
                    path = os.path.join(subdir, file)
                    results.append({'path': path, 'filetype': filetype})
        return results

class Settings:
    def __init__(self, fileio: FileOps):
        self.fileio = fileio

    def api_token(self):
        return self.fileio.setting(
            strings.PINBOARD_PROMPT_API_TOKEN, 
            strings.SETTING_API_TOKEN)

    def username(self):
        return self.fileio.setting(
            strings.AO3_PROMPT_USERNAME,
            strings.SETTING_USERNAME)

    def password(self):
        return self.fileio.setting(
            strings.AO3_PROMPT_PASSWORD,
            strings.SETTING_PASSWORD)

    def sleep_time(self) -> int:
        value = self.fileio.get_setting(strings.SETTING_SLEEP_TIME)
        return int(value) if value else strings.DEFAULT_SLEEP_TIME

    def set_sleep_time(self):
        print(strings.PROMPT_SLEEP_TIME)
        value = input()
        try:
            value = int(value)
            if value < 1: value = 1
        except:
            value = 1
        self.fileio.save_setting(strings.SETTING_SLEEP_TIME, value)

    def save_secrets(self):
        value = self.fileio.get_setting(strings.SETTING_SAVE_SECRETS)
        return bool(value) if value else strings.DEFAULT_SAVE_SECRETS

    def set_save_secrets(self):
        print(strings.PROMPT_SAVE_SECRETS)
        value = True if input() == strings.PROMPT_YES else False
        self.fileio.save_setting(strings.SETTING_SAVE_SECRETS, value)

    def update_folder(self):
        return self.fileio.setting(
            strings.UPDATE_PROMPT_INPUT,
            strings.SETTING_UPDATE_FOLDER)
    
    def download_types(self):
        filetypes = self.fileio.get_setting(strings.SETTING_FILETYPES)
        if isinstance(filetypes, list):
            print(strings.AO3_PROMPT_USE_SAVED_DOWNLOAD_TYPES)
            if input() == strings.PROMPT_YES: return filetypes
        filetypes = []
        while(True):
            filetype = ''
            while filetype not in strings.AO3_ACCEPTABLE_DOWNLOAD_TYPES:
                print(strings.AO3_PROMPT_DOWNLOAD_TYPE)
                filetype = input()
            filetypes.append(filetype)
            print(strings.AO3_INFO_FILE_TYPE.format(filetype))
            print(strings.AO3_PROMPT_DOWNLOAD_TYPES_COMPLETE)
            if input() == strings.PROMPT_YES:
                filetypes = list(set(filetypes))
                self.fileio.save_setting(strings.SETTING_FILETYPES, filetypes)
                return filetypes

    def update_types(self):
        filetypes = self.fileio.get_setting(strings.SETTING_UPDATE_FILETYPES)
        if isinstance(filetypes, list):
            print(strings.UPDATE_PROMPT_USE_SAVED_FILE_TYPES)
            if input() == strings.PROMPT_YES: return filetypes
        filetypes = []
        while(True):
            filetype = ''
            while filetype not in strings.UPDATE_ACCEPTABLE_FILE_TYPES:
                print(strings.UPDATE_PROMPT_FILE_TYPE)
                filetype = input()
            filetypes.append(filetype)
            print(strings.UPDATE_INFO_FILE_TYPE.format(filetype))
            print(strings.AO3_PROMPT_DOWNLOAD_TYPES_COMPLETE)
            if input() == strings.PROMPT_YES:
                filetypes = list(set(filetypes))
                self.fileio.save_setting(strings.SETTING_UPDATE_FILETYPES, filetypes)
                return filetypes

class Repository:
    PAUSE_TIME = 300
    AO3_LOGIN_URL = 'https://archiveofourown.org/users/login'
    HEADERS = {'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit'
               '/537.36 (KHTML, like Gecko) Chrome/60.0.3112.113 Safari/537.36 +nianeyna@gmail.com'}

    def __init__(self, soup: SoupParse, settings: Settings):
        self.soup = soup
        self.session = requests.sessions.Session()
        self.sleep_time = settings.sleep_time()

    def get_soup(self, url: str) -> BeautifulSoup:
        """Get BeautifulSoup object from a url."""

        html = self.my_get(url).text
        soup = BeautifulSoup(html, 'html.parser')
        return soup

    def get_book(self, url: str) -> bytes:
        """Get content from url. Intended for downloading works from ao3."""

        return self.my_get(url).content

    def my_get(self, url: str) -> requests.Response:
        """Get response from a url."""

        response = self.session.get(url, headers=self.HEADERS)

        if response.status_code == codes['too_many_requests']:
            print(strings.MESSAGE_TOO_MANY_REQUESTS.format(datetime.datetime.now().strftime('%H:%M:%S')))
            sleep(self.PAUSE_TIME)
            print(strings.MESSAGE_RESUMING)
            return self.my_get(url)

        if('archiveofourown.org' in url):
            sleep(self.sleep_time)
        
        return response

    def login(self, username: str, password: str) -> None:
        """Login to ao3."""

        thesoup = self.get_soup(self.AO3_LOGIN_URL)
        token = self.soup.get_token(thesoup)
        payload = self.get_payload(username, password, token)
        response = self.session.post(self.AO3_LOGIN_URL, data=payload)
        thesoup = BeautifulSoup(response.text, 'html.parser')
        if self.soup.is_failed_login(thesoup):
            raise LoginException(strings.ERROR_FAILED_LOGIN)

class Ao3Base:
    def __init__(self, fileops: FileOps, textparse: TextParse, soup: SoupParse, repo: Repository):
        self.fileops = fileops
        self.textparse = textparse
        self.soup = soup
        self.repo = repo

class Ao3:
    def __init__(self, base: Ao3Base, filetypes: list[str], images: bool, series: bool, pages: int):
        self.base = base
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

        if strings.AO3_IDENTIFIER_WORK in link:
            if link not in links_list:
                links_list.append(link)
        elif strings.AO3_IDENTIFIER_SERIES in link:
            if self.series:
                series_soup = self.base.repo.get_soup(link)
                proceed_link = self.base.soup.proceed(series_soup)
                series_soup = self.base.repo.get_soup(proceed_link)
                work_urls = self.base.soup.get_work_urls(series_soup)
                for work_url in work_urls:
                    if work_url not in links_list:
                        links_list.append(work_url)
        elif strings.AO3_IDENTIFIER in link:
            while True:
                thesoup = self.base.repo.get_soup(link)
                urls = self.base.soup.get_work_and_series_urls(thesoup) if self.series else self.base.soup.get_work_urls(thesoup)
                if all(x in self.visited for x in urls): break
                for url in urls:
                    self.get_work_links_recursive(url, links_list)
                link = self.base.textparse.get_next_page(link)
                pagenum = self.base.textparse.get_page_number(link)
                if self.pages and pagenum == self.pages + 1: 
                    break
                else:
                    print(strings.INFO_FINISHED_PAGE.format(str(pagenum - 1), str(pagenum)))
    
    def download_recursive(self, link: str) -> None:
        if link in self.visited: return
        self.visited.append(link)

        if strings.AO3_IDENTIFIER_WORK in link:
            self.log = {}
            self.download_work(link, None)
        elif strings.AO3_IDENTIFIER_SERIES in link:
            if self.series:
                self.log = {}
                self.download_series(link)
        elif strings.AO3_IDENTIFIER in link:
            while True:
                thesoup = self.base.repo.get_soup(link)
                urls = self.base.soup.get_work_and_series_urls(thesoup)
                if all(x in self.visited for x in urls): break
                for url in urls:
                    self.download_recursive(url)
                link = self.base.textparse.get_next_page(link)
                pagenum = self.base.textparse.get_page_number(link)
                if self.pages and pagenum == self.pages + 1: 
                    break
                else:
                    self.fileio.write_log({'starting': link})
                    print(strings.INFO_FINISHED_PAGE.format(str(pagenum - 1), str(pagenum)))
        else:
            raise InvalidLinkException(strings.ERROR_INVALID_LINK)

    def download_series(self, link: str) -> None:
        try:
            series_soup = self.base.repo.get_soup(link)
            proceed_link = self.base.soup.proceed(series_soup)
            series_soup = self.base.repo.get_soup(proceed_link)
            series_info = self.base.soup.get_series_info(series_soup)
            series_title = series_info.title
            self.log['series'] = series_title
            for work_url in series_info.works:
                if work_url not in self.visited:
                    self.visited.append(work_url)
                    self.download_work(work_url, None)
        except Exception as e:
            self.log['link'] = link
            self.log_error(e)

    def download_work(self, link: str, chapters: str) -> None:
        try:
            self.log['link'] = link

            thesoup = self.base.repo.get_soup(link)
            proceed_link = self.base.soup.proceed(thesoup)
            thesoup = self.base.repo.get_soup(proceed_link)

            title = self.base.soup.get_title(thesoup)
            filename = self.base.fileio.get_valid_filename(title)
            self.log['title'] = title

            if chapters is not None:
                currentchapters = self.base.soup.get_current_chapters(thesoup)
                if currentchapters <= chapters: return

            for filetype in self.filetypes:
                link = self.base.soup.get_download_link(thesoup, filetype)
                response = self.base.repo.get_book(link)
                filetype = self.base.textparse.get_file_type(filetype)
                self.base.fileops.save_bytes(filename + filetype, response)

            if self.images:
                imagelog = {'link': link, 'title': title}
                imagelinks = self.soup.get_image_links(thesoup)
                self.base.fileio.make_dir(strings.IMAGE_FOLDER_NAME)
                self.save_images(imagelinks, filename, imagelog)

        except Exception as e:
            self.log_error(e)
        else:
            self.log['success'] = True
            self.fileio.write_log(self.log)

    def save_images(self, imagelinks, filename, imagelog):
        counter = 0
        for img in imagelinks:
            imagelog['imagelink'] = img
            if str.startswith(img, '/'): break
            try:
                ext = os.path.splitext(img)[1]
                if '?' in ext: ext = ext[:ext.index('?')]
                response = self.base.repo.get_book(img)
                imagefile = filename + ' img' + str(counter).zfill(3) + ext
                self.base.fileio.save_bytes(os.path.join(strings.IMAGE_FOLDER_NAME, imagefile), response)
                counter += 1
            except Exception as e:
                imagelog['error'] = str(e)
                imagelog['message'] = strings.ERROR_IMAGE
                imagelog['stacktrace'] = traceback.format_exc()
                self.base.fileio.write_log(imagelog)

    def log_error(self, exception: Exception):
        self.log['error'] = str(exception)
        self.log['success'] = False
        if not isinstance(exception, Ao3DownloaderException):
            self.log['stacktrace'] = ''.join(traceback.TracebackException.from_exception(exception).format())
        self.base.fileio.write_log(self.log)

class Pinboard:
    POSTS_FROM_DATE_URL = 'https://api.pinboard.in/v1/posts/all?auth_token={}&fromdt={}'
    ALL_POSTS_URL = 'https://api.pinboard.in/v1/posts/all?auth_token={}'
    TIMESTAMP_URL = '{}-{}-{}T00:00:00Z'

    def __init__(self, repo: Repository, api_token: str):
        self.repo = repo
        self.api_token = api_token

    def get_bookmarks(self, date: datetime.datetime, exclude_toread: bool) -> list[dict[str, str]]:
        url = self.get_pinboard_url(self.api_token, date)
        content = self.repo.get_book(url)
        bookmark_xml = ET.XML(content)
        return self.get_bookmark_list(bookmark_xml, exclude_toread)

    def get_pinboard_url(self, date: datetime.datetime) -> str:
        if date == None:
            return self.ALL_POSTS_URL.format(self.api_token)
        else:
            year = str(date.year)
            month = str(date.month).zfill(2)
            day = str(date.day).zfill(2)
            timestamp = self.TIMESTAMP_URL.format(year, month, day)
            return self.POSTS_FROM_DATE_URL.format(self.api_token, timestamp)

    def get_bookmark_list(self, bookmark_xml: ET.Element, exclude_toread: bool) -> list[dict[str, str]]:
        bookmark_list = []
        for child in bookmark_xml:
            attributes = child.attrib
            # only include valid ao3 links
            if strings.AO3_IDENTIFIER_WORK in attributes['href'] or strings.AO3_IDENTIFIER_SERIES in attributes['href']:
                # if exclude_toread is true, only include read bookmarks
                if exclude_toread:
                    if not 'toread' in attributes:
                        bookmark_list.append(attributes)          
                # otherwise include all valid bookmarks
                else:
                    bookmark_list.append(attributes)
        return bookmark_list

class Update:
    def __init__(self, soup: SoupParse, pdfparse: PdfParse, xmlparse: XmlParse, update: bool, update_series: bool):
        self.soup = soup
        self.pdfparse = pdfparse
        self.xmlparse = xmlparse
        self.update = update
        self.update_series = update_series

    def process_file(self, path: str, filetype: str) -> dict:

        workinfo = self.get_work_info(path, filetype)

        if workinfo.link is None: return None # if this isn't a work from ao3, return
        
        # if we don't care whether the fic is incomplete, just return the work link
        if not self.update: return {'link': workinfo.link}

        # if this is a series update, return the series links if any were found
        if self.update_series: return {'link': workinfo.link, 'series': workinfo.series} if workinfo.series else None

        # otherwise continue checking for incomplete fics
        if workinfo.stats is None: return None # if we can't find the series metadata, return

        # if the series metadata does not contain the character "/", return
        # we assume that the "/" character represents chapter count
        index = workinfo.stats.find('/')
        if index == -1: return None

        # if the chapter counts do not match, we assume the work is incomplete
        totalchap = TextParse().get_total_chapters(workinfo.stats, index)
        currentchap = TextParse().get_current_chapters(workinfo.stats, index)

        # if the work is incomplete, return the info
        if currentchap != totalchap:
            return {'link': workinfo.link, 'chapters': currentchap}

    def get_work_info(self, path: str, filetype: str) -> FicFileInfo:

        if filetype == 'EPUB':
            xml = self.get_epub_preface(path)
            href = self.xmlparse.get_work_link_epub(xml)
            stats = self.xmlparse.get_stats_epub(xml)
            series = self.xmlparse.get_series_epub(xml)
            workinfo = FicFileInfo(href, stats, series)

        elif filetype == 'HTML':
            with open(path, 'r', encoding='utf-8') as f:
                soup = BeautifulSoup(f, 'html.parser')
                href = self.soup.get_work_link_html(soup)
                stats = self.soup.get_stats_html(soup)
                series = self.soup.get_series_html(soup)
                workinfo = FicFileInfo(href, stats, series)

        elif filetype == 'AZW3':
            tempdir, filepath = mobi.extract(path)
            try:
                if os.path.splitext(filepath)[1].upper()[1:] != 'EPUB':
                    # assuming all AO3 AZW3 files are packaged in the same way (why wouldn't they be?) 
                    # we can take this as an indication that the source of this file was not AO3
                    return None
                # the extracted epub is formatted the same way as the regular epubs, yay
                xml = self.get_epub_preface(filepath)
                href = self.xmlparse.get_work_link_epub(xml)
                stats = self.xmlparse.get_stats_epub(xml)
                series = self.xmlparse.get_series_epub(xml)
                workinfo = FicFileInfo(href, stats, series)
            finally:
                # putting this in a finally block *should* ensure that 
                # I never accidentally leave temp files lying around
                # (unless mobi somehow messes up which I can't control)
                shutil.rmtree(tempdir) 

        elif filetype == 'MOBI':
            tempdir, filepath = mobi.extract(path)
            try:
                if os.path.splitext(filepath)[1].upper()[1:] != 'HTML':
                    return None
                with open(filepath, 'r', encoding='utf-8') as f:
                    soup = BeautifulSoup(f, 'html.parser')
                    href = self.soup.get_work_link_mobi(soup)
                    stats = self.soup.get_stats_mobi(soup)
                    series = self.soup.get_series_mobi(soup)
                    workinfo = FicFileInfo(href, stats, series)
            finally:
                shutil.rmtree(tempdir)

        elif filetype == 'PDF':
            pdf = pdfquery.PDFQuery(path, input_text_formatter='utf-8')
            try:
                pdf.load(0, 1, 2) # load the first 3 pages. please god no one has a longer tag wall than that.
            except StopIteration:
                pdf.load() # handle pdfs with fewer than 3 pages
            href = self.pdfparse.get_work_link_pdf(pdf)
            stats = self.pdfparse.get_stats_pdf(pdf)
            series = self.pdfparse.get_series_pdf(pdf)
            workinfo = FicFileInfo(href, stats, series)

        else:
            raise ValueError('Invalid filetype argument: {}. Valid filetypes are '.format(filetype) + ','.join(strings.UPDATE_ACCEPTABLE_FILE_TYPES))

        return workinfo

    def get_epub_preface(path: str) -> ET.Element:
        book = epub.read_epub(path)
        preface = list(book.get_items_of_type(ebooklib.ITEM_DOCUMENT))[0]
        content = preface.get_content().decode('utf-8')
        return ET.fromstring(content)

class Actions:
    def __init__(self) -> None:
        self.fileops = FileOps()
        self.pdfparse = PdfParse()
        self.xmlparse = XmlParse()
        self.textparse = TextParse()
        self.soupparse = SoupParse(self.textparse)
        self.settings = Settings(self.fileops)
        self.repository = Repository(self.soupparse, self.settings)
        self.ao3base = Ao3Base(self.fileops, self.textparse, self.soupparse, self.repository)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        self.repository.session.close()

    def ao3_login(self) -> None:

        print(strings.AO3_PROMPT_LOGIN)
        login = False if input() == strings.PROMPT_NO else True

        if login:
            username = self.settings.username()
            password = self.settings.password()
            print(strings.AO3_INFO_LOGIN)
            try:
                self.repository.login(username, password)
            except LoginException:
                self.fileops.save_setting(strings.SETTING_USERNAME, None)
                self.fileops.save_setting(strings.SETTING_PASSWORD, None)
                raise
    
    def action_ao3(self) -> None:

        filetypes = self.settings.download_types()

        print(strings.AO3_PROMPT_SERIES)
        series = True if input() == strings.PROMPT_YES else False
        
        latest = None
        try:
            with open(self.fileops.logfile, 'r', encoding='utf-8') as f:
                objects = map(lambda x: json.loads(x), f.readlines())
                starts = filter(lambda x: 'starting' in x, objects)
                bydate = sorted(starts, key=lambda x: datetime.datetime.strptime(x['timestamp'], '%m/%d/%Y, %H:%M:%S'), reverse=True)
                if bydate: latest = bydate[0]
        except FileNotFoundError:
            pass
        except Exception as e:
            self.fileops.write_log({'error': str(e), 'message': strings.ERROR_LOG_FILE, 'stacktrace': traceback.format_exc()})

        link = None
        if latest:
            print(strings.AO3_PROMPT_LAST_PAGE)
            if input() == strings.PROMPT_YES:
                link = latest['starting']

        if not link: 
            print(strings.AO3_PROMPT_LINK)
            link = input()

        print(strings.AO3_PROMPT_PAGES)
        pages = input()

        try:
            pages = int(pages)
            if pages <= 0:
                pages = None
        except:
            pages = None

        print(strings.AO3_PROMPT_IMAGES)
        images = True if input() == strings.PROMPT_YES else False

        self.ao3_login()

        print(strings.AO3_INFO_DOWNLOADING)

        self.fileops.write_log({'starting': link})

        Ao3(self.ao3base, filetypes, images, series, pages).download(link)

    def action_getlinks(self) -> None:

        print(strings.AO3_PROMPT_LINK)
        link = input()

        print(strings.AO3_PROMPT_SERIES)
        series = True if input() == strings.PROMPT_YES else False

        print(strings.AO3_PROMPT_PAGES)
        pages = input()

        try:
            pages = int(pages)
            if pages <= 0:
                pages = None
        except:
            pages = None

        self.ao3_login()

        links = Ao3(self.ao3base, None, False, series, pages).get_work_links(link)

        filename = f'links_{datetime.datetime.now().strftime("%m%d%Y%H%M%S")}.txt'

        with open(os.path.join(strings.DOWNLOAD_FOLDER_NAME, filename), 'w') as f:
            for l in links:
                f.write(l + '\n')

    def action_redownload(self) -> None:

        print(strings.REDOWNLOAD_PROMPT_FOLDER)
        folder = input()

        oldtypes = []
        while True:
            filetype = ''
            while filetype not in strings.UPDATE_ACCEPTABLE_FILE_TYPES:
                print(strings.REDOWNLOAD_PROMPT_FILE_TYPE)
                filetype = input()
            oldtypes.append(filetype)
            print(strings.REDOWNLOAD_INFO_FILE_TYPE.format(filetype))
            print(strings.AO3_PROMPT_DOWNLOAD_TYPES_COMPLETE)
            if input() == strings.PROMPT_YES:
                oldtypes = list(set(oldtypes))
                break

        newtypes = []
        while True:
            filetype = ''
            while filetype not in strings.AO3_ACCEPTABLE_DOWNLOAD_TYPES:
                print(strings.AO3_PROMPT_DOWNLOAD_TYPE)
                filetype = input()
            newtypes.append(filetype)
            print(strings.AO3_INFO_FILE_TYPE.format(filetype))
            print(strings.AO3_PROMPT_DOWNLOAD_TYPES_COMPLETE)
            if input() == strings.PROMPT_YES:
                newtypes = list(set(newtypes))
                break

        print(strings.AO3_PROMPT_IMAGES)
        images = True if input() == strings.PROMPT_YES else False

        self.ao3_login()

        fics = self.fileops.get_files_of_type(folder, oldtypes)
        
        print(strings.UPDATE_INFO_NUM_RETURNED.format(len(fics)))

        print(strings.REDOWNLOAD_INFO_URLS)

        update = Update(self.soupparse, self.pdfparse, self.xmlparse, False, False)

        works = []
        for fic in tqdm(fics):
            try:
                work = update.process_file(fic['path'], fic['filetype'])
                if work: 
                    works.append(work)
                    self.fileops.write_log({'message': strings.MESSAGE_FIC_FILE, 'path': fic['path'], 'link': work['link']})
            except Exception as e:
                self.fileops.write_log({'message': strings.ERROR_REDOWNLOAD, 'path': fic['path'], 'error': str(e), 'stacktrace': traceback.format_exc()})

        urls = list(set(map(lambda x: x['link'], works)))

        print(strings.REDOWNLOAD_INFO_DONE.format(len(urls)))

        logs = self.fileops.load_logfile()
        if logs:
            print(strings.INFO_EXCLUDING_WORKS)
            titles = self.textparse.get_title_dict(logs)
            unsuccessful = self.textparse.get_unsuccessful_downloads(logs)
            urls = list(filter(lambda x: 
                not self.fileops.file_exists(x, titles, newtypes)
                and x not in unsuccessful,
                urls))

        print(strings.AO3_INFO_DOWNLOADING)

        ao3 = Ao3(self.ao3base, newtypes, images, False, None)

        for url in tqdm(urls):
            ao3.download(url)

    def action_update(self) -> None:

        folder = self.fileops.setting(
            strings.UPDATE_PROMPT_INPUT,
            strings.SETTING_UPDATE_FOLDER)

        update_filetypes = self.settings.update_types()
        download_filetypes = self.settings.download_types()

        print(strings.AO3_PROMPT_IMAGES)
        images = True if input() == strings.PROMPT_YES else False

        self.ao3_login()

        print(strings.UPDATE_INFO_FILES)

        fics = self.fileops.get_files_of_type(folder, update_filetypes)
        
        print(strings.UPDATE_INFO_NUM_RETURNED.format(len(fics)))

        print(strings.UPDATE_INFO_URLS)

        update = Update(self.soupparse, self.pdfparse, self.xmlparse, True, False)

        works = []
        for fic in tqdm(fics):
            try:
                work = update.process_file(fic['path'], fic['filetype'])
                if work:
                    works.append(work)
                    self.fileops.write_log({'message': strings.MESSAGE_INCOMPLETE_FIC, 'path': fic['path'], 'link': work['link']})
            except Exception as e:
                self.fileops.write_log({'message': strings.ERROR_INCOMPLETE_FIC, 'path': fic['path'], 'error': str(e), 'stacktrace': traceback.format_exc()})    

        # remove duplicate work links. take lowest number of chapters.
        works_cleaned = []
        works_sorted = sorted(works, key=lambda x: x['link'])
        for link, group in itertools.groupby(works_sorted, lambda x: x['link']):
            chapters = min(group, key=lambda x: x['chapters'])['chapters']
            works_cleaned.append({'link': link, 'chapters': chapters})

        print(strings.UPDATE_INFO_URLS_DONE)

        print(strings.UPDATE_INFO_DOWNLOADING)

        ao3 = Ao3(self.ao3base, download_filetypes, images, False, None)

        for work in tqdm(works_cleaned):
            ao3.update(work['link'], work['chapters'])

    def action_updateseries(self) -> None:

        folder = self.settings.update_folder()
        update_filetypes = self.settings.update_types()
        download_filetypes = self.settings.download_types()

        print(strings.AO3_PROMPT_IMAGES)
        images = True if input() == strings.PROMPT_YES else False

        self.ao3_login()

        print(strings.UPDATE_INFO_FILES)

        files = self.fileops.get_files_of_type(folder, update_filetypes)
        
        print(strings.UPDATE_INFO_NUM_RETURNED.format(len(files)))

        print(strings.SERIES_INFO_FILES)

        update = Update(self.soupparse, self.pdfparse, self.xmlparse, True, True)

        works = []
        for file in tqdm(files):
            try:
                work = update.process_file(file['path'], file['filetype'])
                if work:
                    works.append(work)
                    self.fileops.write_log({'message': strings.MESSAGE_SERIES_FILE, 'path': file['path'], 'link': work['link'], 'series': work['series']})
            except Exception as e:
                self.fileops.write_log({'message': strings.ERROR_FIC_IN_SERIES, 'path': file['path'], 'error': str(e), 'stacktrace': traceback.format_exc()})    

        print(strings.SERIES_INFO_URLS)

        series = dict[str, list[str]]()
        for work in works:
            for s in work['series']:
                if s not in series:
                    series[s] = []
                link = work['link'].replace('http://', 'https://')
                if link not in series[s]:
                    series[s].append(link)

        print(strings.SERIES_INFO_NUM.format(len(series)))

        print(strings.SERIES_INFO_DOWNLOADING)

        ao3 = Ao3(self.ao3base, download_filetypes, images, True, None)

        for key, value in tqdm(series.items()):
            ao3.update_series(key, value)

    def action_pinboard(self) -> None:

        filetypes = self.settings.download_types()

        print(strings.PINBOARD_PROMPT_DATE)
        getdate = True if input() == strings.PROMPT_YES else False
        if getdate:
            date_format = 'mm/dd/yyyy'
            print(strings.PINBOARD_PROMPT_ENTER_DATE.format(date_format))
            inputdate = input()
            date = datetime.strptime(inputdate, '%m/%d/%Y')
        else:
            date = None

        print(strings.PINBOARD_PROMPT_INCLUDE_UNREAD)
        exclude_toread = False if input() == strings.PROMPT_YES else True

        print(strings.AO3_PROMPT_IMAGES)
        images = True if input() == strings.PROMPT_YES else False

        api_token = self.settings.api_token()

        self.ao3_login()
        
        print(strings.PINBOARD_INFO_GETTING_BOOKMARKS)
        bookmarks = Pinboard(self.repository, api_token).get_bookmarks(date, exclude_toread)
        print(strings.PINBOARD_INFO_NUM_RETURNED.format(len(bookmarks)))

        logs = self.fileops.load_logfile()
        if logs:
            print(strings.INFO_EXCLUDING_WORKS)
            titles = self.textparse.get_title_dict(logs)
            unsuccessful = self.textparse.get_unsuccessful_downloads(logs)
            bookmarks = list(filter(lambda x: 
                not self.fileops.file_exists(x['href'], titles, filetypes) 
                and x['href'] not in unsuccessful, 
                bookmarks))

        print(strings.AO3_INFO_DOWNLOADING)

        ao3 = Ao3(self.ao3base, filetypes, images, True, None)

        for item in tqdm(bookmarks):
            ao3.download(item['href'])
        
    def action_logvisualization(self) -> None:

        keys = ['timestamp'] # always put timestamp first
        data = []

        logfile = os.path.join(strings.LOG_FOLDER_NAME, strings.LOG_FILE_NAME)
        visfile = os.path.join(strings.LOG_FOLDER_NAME, strings.VISUALIZATION_FILE_NAME)

        if not os.path.exists(logfile):
            print(strings.INFO_NO_LOG_FILE)
            return

        with open(logfile, 'r', encoding='utf-8') as f:
            for line in f:
                js = json.loads(line)
                if 'starting' not in js:
                    for key in js:
                        if key not in keys:
                            keys.append(key)
                    data.append(js)

        for item in data:
            for key in keys:
                if key not in item:
                    item[key] = ''

        thead = '<thead><tr>'
        for key in keys:
            thead += '<th>' + key + '</th>'
        thead += '</tr></thead>'

        tbody = '<tbody>'
        for item in data:
            tr = '<tr>'
            for key in keys:
                key_item = str(item[key])
                tr += '<td>' + key_item + '</td>'
            tr += '</tr>'
            tbody += tr
        tbody += '</tbody>'

        table = thead + tbody

        with open(strings.TEMPLATE_FILE_NAME, encoding='utf-8') as f:
            template = f.read()

        logvisualization = template.replace('%TABLE%', table)

        with open (visfile, 'w', encoding='utf-8') as f:
            f.write(logvisualization)
