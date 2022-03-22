import requests
import traceback

import ao3downloader.actions.shared as shared
import ao3downloader.fileio as fileio
import ao3downloader.strings as strings
import ao3downloader.update as update

from tqdm import tqdm

from ao3downloader.ao3 import Ao3

def action():

    folder = fileio.setting(
        strings.UPDATE_PROMPT_INPUT, 
        strings.SETTINGS_FILE_NAME, 
        strings.SETTING_UPDATE_FOLDER)

    update_filetypes = shared.get_update_types()
    download_filetypes = shared.get_download_types()

    print(strings.AO3_PROMPT_IMAGES)
    images = True if input() == strings.PROMPT_YES else False

    session = requests.sessions.Session()
    shared.ao3_login(session)

    print(strings.UPDATE_INFO_FILES)

    files = shared.get_files_of_type(folder, update_filetypes)
    
    print(strings.UPDATE_INFO_NUM_RETURNED.format(len(files)))

    print(strings.SERIES_INFO_FILES)

    logfile = shared.get_logfile()

    works = []
    for file in tqdm(files):
        try:
            work = update.process_file(file['path'], file['filetype'], True, True)
            if work:
                works.append(work)
                fileio.write_log(logfile, {'message': strings.MESSAGE_SERIES_FILE, 'path': file['path'], 'link': work['link'], 'series': work['series']})
        except Exception as e:
            fileio.write_log(logfile, {'message': strings.ERROR_FIC_IN_SERIES, 'path': file['path'], 'error': str(e), 'stacktrace': traceback.format_exc()})    

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

    fileio.make_dir(strings.DOWNLOAD_FOLDER_NAME)

    ao3 = Ao3(session, logfile, strings.DOWNLOAD_FOLDER_NAME, download_filetypes, images, True, None)

    for key, value in tqdm(series.items()):
        ao3.update_series(key, value)
