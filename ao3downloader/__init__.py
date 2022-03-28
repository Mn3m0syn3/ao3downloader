import datetime
import json
import os
import re

from bs4 import BeautifulSoup
from requests import codes, get
from time import sleep

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

class FileOps:
    def __init__(self, textparse: TextParse):
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
    def __init__(self, soup: Soup, settings: Settings):
        self.soup = soup
        self.session = requests.sessions.Session()
        self.sleep_time = settings.sleep_time()
        self.pause_time = 300
        self.ao3_login_url = 'https://archiveofourown.org/users/login'
        self.headers = {'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit'
                        '/537.36 (KHTML, like Gecko) Chrome/60.0.3112.113 Safari/537.36 +nianeyna@gmail.com'}

    def get_soup(self, url):
        """Get BeautifulSoup object from a url."""

        html = self.my_get(url).text
        soup = BeautifulSoup(html, 'html.parser')
        return soup

    def get_book(self, url):
        """Get content from url. Intended for downloading works from ao3."""

        return self.my_get(url).content

    def my_get(self, url):
        """Get response from a url."""

        if self.session == None:
            response = get(url, headers=self.headers)
        else:
            response = self.session.get(url, headers=self.headers)

        if response.status_code == codes['too_many_requests']:
            print(strings.MESSAGE_TOO_MANY_REQUESTS.format(datetime.datetime.now().strftime('%H:%M:%S')))
            sleep(self.pause_time)
            print(strings.MESSAGE_RESUMING)
            return self.my_get(url)

        if('archiveofourown.org' in url):
            sleep(self.sleep_time)
            
        return response

    def login(self, username, password):
        """Login to ao3."""

        soup = self.get_soup(self.ao3_login_url)
        token = self.soup.get_token(soup)
        payload = self.get_payload(username, password, token)
        response = self.session.post(ao3_login_url, data=payload)
        soup = BeautifulSoup(response.text, 'html.parser')
        if self.soup.is_failed_login(soup):
            raise LoginException(strings.ERROR_FAILED_LOGIN)
