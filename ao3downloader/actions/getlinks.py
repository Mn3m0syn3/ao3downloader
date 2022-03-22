import datetime
import os
import requests

import ao3downloader.actions.shared as shared
import ao3downloader.fileio as fileio
import ao3downloader.strings as strings

from ao3downloader.ao3 import Ao3

def action():

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

    session = requests.sessions.Session()

    shared.ao3_login(session)

    links = Ao3(session, None, None, None, False, series, pages).get_work_links(link)

    fileio.make_dir(strings.DOWNLOAD_FOLDER_NAME)
    filename = f'links_{datetime.datetime.now().strftime("%m%d%Y%H%M%S")}.txt'

    with open(os.path.join(strings.DOWNLOAD_FOLDER_NAME, filename), 'w') as f:
        for l in links:
            f.write(l + '\n')
