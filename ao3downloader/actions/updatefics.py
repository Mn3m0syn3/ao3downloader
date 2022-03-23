import itertools
import requests
import traceback

import ao3downloader.actions.shared as shared
import ao3downloader.strings as strings
import ao3downloader.update as update

from tqdm import tqdm

from ao3downloader.ao3 import Ao3
from ao3downloader.fileio import FileOps
from ao3downloader.repo import Repository


def action():

    logfile = shared.get_logfile()
    fileio = FileOps(strings.DOWNLOAD_FOLDER_NAME, logfile, strings.SETTINGS_FILE_NAME)

    folder = fileio.setting(
        strings.UPDATE_PROMPT_INPUT,
        strings.SETTING_UPDATE_FOLDER)

    update_filetypes = shared.get_update_types()
    download_filetypes = shared.get_download_types()

    print(strings.AO3_PROMPT_IMAGES)
    images = True if input() == strings.PROMPT_YES else False

    session = requests.sessions.Session()
    repo = Repository(session, 1)
    shared.ao3_login(repo)

    print(strings.UPDATE_INFO_FILES)

    fics = shared.get_files_of_type(folder, update_filetypes)
    
    print(strings.UPDATE_INFO_NUM_RETURNED.format(len(fics)))

    print(strings.UPDATE_INFO_URLS)

    works = []
    for fic in tqdm(fics):
        try:
            work = update.process_file(fic['path'], fic['filetype'])
            if work:
                works.append(work)
                fileio.write_log({'message': strings.MESSAGE_INCOMPLETE_FIC, 'path': fic['path'], 'link': work['link']})
        except Exception as e:
            fileio.write_log({'message': strings.ERROR_INCOMPLETE_FIC, 'path': fic['path'], 'error': str(e), 'stacktrace': traceback.format_exc()})    

    # remove duplicate work links. take lowest number of chapters.
    works_cleaned = []
    works_sorted = sorted(works, key=lambda x: x['link'])
    for link, group in itertools.groupby(works_sorted, lambda x: x['link']):
        chapters = min(group, key=lambda x: x['chapters'])['chapters']
        works_cleaned.append({'link': link, 'chapters': chapters})

    print(strings.UPDATE_INFO_URLS_DONE)

    print(strings.UPDATE_INFO_DOWNLOADING)

    ao3 = Ao3(repo, fileio, download_filetypes, images, False, None)

    for work in tqdm(works_cleaned):
        ao3.update(work['link'], work['chapters'])

    session.close()
