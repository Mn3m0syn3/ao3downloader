"""Web requests go here."""

import datetime

import ao3downloader.strings as strings

from bs4 import BeautifulSoup
from time import sleep
from requests import codes
from requests import get

from ao3downloader.soup import get_token
from ao3downloader.soup import is_failed_login

from ao3downloader.exceptions import LoginException


class Repository:
    def __init__(self, sleep_time):
        self.session = requests.sessions.Session()
        self.sleep_time = sleep_time
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
        token = get_token(soup)
        payload = self.get_payload(username, password, token)
        response = self.session.post(ao3_login_url, data=payload)
        soup = BeautifulSoup(response.text, 'html.parser')
        if is_failed_login(soup):
            raise LoginException(strings.ERROR_FAILED_LOGIN)


    def get_payload(username, password, token):
        """Get payload for ao3 login."""

        payload = {
            'user[login]': username,
            'user[password]': password,
            'user[remember_me]': '1',
            'utf8': '&#x2713;',
            'authenticity_token': token
        }
        return payload
