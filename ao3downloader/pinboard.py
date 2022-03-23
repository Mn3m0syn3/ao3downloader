"""Logic to get bookmarks from pinboard."""

import xml.etree.ElementTree as ET
from datetime import datetime
from ao3downloader.repo import Repository


class Pinboard:
    def __init__(self, repo: Repository, api_token: str):
        self.repo = repo
        self.api_token = api_token
        self.POSTS_FROM_DATE_URL = 'https://api.pinboard.in/v1/posts/all?auth_token={}&fromdt={}'
        self.ALL_POSTS_URL = 'https://api.pinboard.in/v1/posts/all?auth_token={}'
        self.TIMESTAMP_URL = '{}-{}-{}T00:00:00Z'


    def get_bookmarks(self, date: datetime, exclude_toread: bool) -> list[dict[str, str]]:
        url = self.get_pinboard_url(api_token, date)
        content = self.repo.get_book(url)
        bookmark_xml = ET.XML(content)
        return self.get_bookmark_list(bookmark_xml, exclude_toread)


    def get_pinboard_url(self, date: datetime) -> str:
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
            if self.is_work_or_series(attributes):
                # if exclude_toread is true, only include read bookmarks
                if exclude_toread:
                    if self.have_read(attributes):
                        bookmark_list.append(attributes)          
                # otherwise include all valid bookmarks
                else:
                    bookmark_list.append(attributes)
        return bookmark_list


    def have_read(bookmark_attributes):
        return not 'toread' in bookmark_attributes


    def is_work_or_series(self, bookmark_attributes):
        return self.is_work(bookmark_attributes) or self.is_series(bookmark_attributes)


    def is_work(bookmark_attributes):
        return 'archiveofourown.org/works/' in bookmark_attributes['href']


    def is_series(bookmark_attributes):
        return 'archiveofourown.org/series/' in bookmark_attributes['href']
