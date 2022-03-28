import datetime
import os
import requests

import ao3downloader.actions.shared as shared
import ao3downloader.strings as strings

from ao3downloader.ao3 import Ao3
from ao3downloader.fileio import FileOps
from ao3downloader.repo import Repository
from ao3downloader.settings import Settings
from ao3downloader.soup import Soup

def action():
    soup = Soup()
    fileio = FileOps()
    settings = Settings(fileio)
    repository = Repository(settings.sleep_time())

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

    shared.ao3_login(repo)
    
    links = Ao3(repository, fileio, soup, None, False, series, pages).get_work_links(link)

    filename = f'links_{datetime.datetime.now().strftime("%m%d%Y%H%M%S")}.txt'

    with open(os.path.join(strings.DOWNLOAD_FOLDER_NAME, filename), 'w') as f:
        for l in links:
            f.write(l + '\n')
