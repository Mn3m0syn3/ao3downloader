import requests

import ao3downloader.actions.shared as shared
import ao3downloader.fileio as fileio
import ao3downloader.pinboard as pinboard
import ao3downloader.strings as strings

from datetime import datetime
from tqdm import tqdm

from ao3downloader.ao3 import Ao3
from ao3downloader.fileio import FileOps
from ao3downloader.pinboard import Pinboard
from ao3downloader.repo import Repository
from ao3downloader.settings import Settings


def action():
    fileio = FileOps()
    settings = Settings(fileio)
    repository = Repository(settings)

    filetypes = settings.download_types()

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

    api_token = fileio.setting(
        strings.PINBOARD_PROMPT_API_TOKEN, 
        strings.SETTING_API_TOKEN)

    shared.ao3_login(repository)
    
    print(strings.PINBOARD_INFO_GETTING_BOOKMARKS)
    bookmarks = Pinboard(repo, api_token).get_bookmarks(date, exclude_toread)
    print(strings.PINBOARD_INFO_NUM_RETURNED.format(len(bookmarks)))

    logs = fileio.load_logfile()
    if logs:
        print(strings.INFO_EXCLUDING_WORKS)
        titles = shared.get_title_dict(logs)
        unsuccessful = shared.get_unsuccessful_downloads(logs)
        bookmarks = list(filter(lambda x: 
            not fileio.file_exists(x['href'], titles, filetypes) 
            and x['href'] not in unsuccessful, 
            bookmarks))

    print(strings.AO3_INFO_DOWNLOADING)

    ao3 = Ao3(repository, fileio, filetypes, images, True, None)

    for item in tqdm(bookmarks):
        ao3.download(item['href'])
    
    repository.session.close()
