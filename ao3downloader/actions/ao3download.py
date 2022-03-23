import datetime
import json
import traceback
import requests

import ao3downloader.actions.shared as shared
import ao3downloader.strings as strings

from ao3downloader.ao3 import Ao3
from ao3downloader.fileio import FileOps
from ao3downloader.repo import Repository


def action():
    fileio = FileOps()
    filetypes = shared.get_download_types(fileio)
    session = requests.sessions.Session()
    repo = Repository(session, 1)

    print(strings.AO3_PROMPT_SERIES)
    series = True if input() == strings.PROMPT_YES else False
    
    latest = None
    try:
        with open(fileio.logfile, 'r', encoding='utf-8') as f:
            objects = map(lambda x: json.loads(x), f.readlines())
            starts = filter(lambda x: 'starting' in x, objects)
            bydate = sorted(starts, key=lambda x: datetime.datetime.strptime(x['timestamp'], '%m/%d/%Y, %H:%M:%S'), reverse=True)
            if bydate: latest = bydate[0]
    except FileNotFoundError:
        pass
    except Exception as e:
        fileio.write_log({'error': str(e), 'message': strings.ERROR_LOG_FILE, 'stacktrace': traceback.format_exc()})

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

    shared.ao3_login(repo)

    print(strings.AO3_INFO_DOWNLOADING)

    fileio.write_log({'starting': link})

    Ao3(repo, fileio, filetypes, images, series, pages).download(link)
    
    session.close()
