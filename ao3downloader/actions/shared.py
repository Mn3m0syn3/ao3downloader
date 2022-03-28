import os

import ao3downloader.exceptions as exceptions
import ao3downloader.strings as strings

from ao3downloader.fileio import FileOps
from ao3downloader.repo import Repository
from ao3downloader.settings import Settings


def ao3_login(repo: Repository, fileio: FileOps, settings: Settings) -> None:

    print(strings.AO3_PROMPT_LOGIN)
    login = False if input() == strings.PROMPT_NO else True

    if login:
        username = settings.username()
        password = settings.password()
        print(strings.AO3_INFO_LOGIN)
        try:
            repo.login(username, password)
        except exceptions.LoginException:
            fileio.save_setting(strings.SETTING_USERNAME, None)
            fileio.save_setting(strings.SETTING_PASSWORD, None)
            raise


def get_files_of_type(folder: str, filetypes: list[str]) -> list[dict[str, str]]:
    results = []
    for subdir, dirs, files in os.walk(folder):
        for file in files:
            filetype = os.path.splitext(file)[1].upper()[1:]
            if filetype in filetypes:
                path = os.path.join(subdir, file)
                results.append({'path': path, 'filetype': filetype})
    return results


def get_title_dict(logs: list[dict]) -> dict[str, str]:
    dictionary = {}
    titles = filter(lambda x: 'title' in x and 'link' in x, logs)
    for obj in list(titles):
        link = obj['link']
        if link not in dictionary:
            title = obj['title']
            dictionary[link] = title
    return dictionary


def get_unsuccessful_downloads(logs: list[dict]) -> list[str]:
    links = []
    errors = filter(lambda x:'link' in x and 'success' in x and x['success'] == False, logs)
    for error in errors:
        link = error['link']
        if link not in links: 
            links.append(link)
    return links
