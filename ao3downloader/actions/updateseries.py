import requests
import traceback

import ao3downloader.actions.shared as shared
import ao3downloader.strings as strings
import ao3downloader.update as update

from tqdm import tqdm

from ao3downloader.ao3 import Ao3
from ao3downloader.fileio import FileOps
from ao3downloader.repo import Repository
from ao3downloader.actions.settings import Settings

def action():
    fileio = FileOps()
    settings = Settings(fileio)

    folder = settings.update_folder()
    update_filetypes = settings.update_types()
    download_filetypes = settings.download_types()

    print(strings.AO3_PROMPT_IMAGES)
    images = True if input() == strings.PROMPT_YES else False

    session = requests.sessions.Session()
    repo = Repository(session, 1)
    shared.ao3_login(session)

    print(strings.UPDATE_INFO_FILES)

    files = shared.get_files_of_type(folder, update_filetypes)
    
    print(strings.UPDATE_INFO_NUM_RETURNED.format(len(files)))

    print(strings.SERIES_INFO_FILES)

    works = []
    for file in tqdm(files):
        try:
            work = update.process_file(file['path'], file['filetype'], True, True)
            if work:
                works.append(work)
                fileio.write_log({'message': strings.MESSAGE_SERIES_FILE, 'path': file['path'], 'link': work['link'], 'series': work['series']})
        except Exception as e:
            fileio.write_log({'message': strings.ERROR_FIC_IN_SERIES, 'path': file['path'], 'error': str(e), 'stacktrace': traceback.format_exc()})    

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

    ao3 = Ao3(repo, fileio, download_filetypes, images, True, None)

    for key, value in tqdm(series.items()):
        ao3.update_series(key, value)
