import ao3downloader.strings as strings
from ao3downloader.fileio import FileOps

class Settings:
    def __init__(self, fileio: FileOps):
        self.fileio = fileio
    
    def api_token():
        return fileio.setting(
            strings.PINBOARD_PROMPT_API_TOKEN, 
            strings.SETTING_API_TOKEN)

    def username():
        return fileio.setting(
            strings.AO3_PROMPT_USERNAME,
            strings.SETTING_USERNAME)

    def password():
        return fileio.setting(
            strings.AO3_PROMPT_PASSWORD,
            strings.SETTING_PASSWORD)

    def sleep_time():
        return fileio.setting(
            strings.PROMPT_SLEEP_TIME,
            strings.SETTING_SLEEP_TIME)

    def update_folder():
        return fileio.setting(
            strings.UPDATE_PROMPT_INPUT,
            strings.SETTING_UPDATE_FOLDER)
    
    def download_types():
        filetypes = fileio.get_setting(strings.SETTING_FILETYPES)
        if isinstance(filetypes, list):
            print(strings.AO3_PROMPT_USE_SAVED_DOWNLOAD_TYPES)
            if input() == strings.PROMPT_YES: return filetypes
        filetypes = []
        while(True):
            filetype = ''
            while filetype not in strings.AO3_ACCEPTABLE_DOWNLOAD_TYPES:
                print(strings.AO3_PROMPT_DOWNLOAD_TYPE)
                filetype = input()
            filetypes.append(filetype)
            print(strings.AO3_INFO_FILE_TYPE.format(filetype))
            print(strings.AO3_PROMPT_DOWNLOAD_TYPES_COMPLETE)
            if input() == strings.PROMPT_YES:
                filetypes = list(set(filetypes))
                fileio.save_setting(strings.SETTING_FILETYPES, filetypes)
                return filetypes

    def update_types():
        filetypes = fileio.get_setting(strings.SETTING_UPDATE_FILETYPES)
        if isinstance(filetypes, list):
            print(strings.UPDATE_PROMPT_USE_SAVED_FILE_TYPES)
            if input() == strings.PROMPT_YES: return filetypes
        filetypes = []
        while(True):
            filetype = ''
            while filetype not in strings.UPDATE_ACCEPTABLE_FILE_TYPES:
                print(strings.UPDATE_PROMPT_FILE_TYPE)
                filetype = input()
            filetypes.append(filetype)
            print(strings.UPDATE_INFO_FILE_TYPE.format(filetype))
            print(strings.AO3_PROMPT_DOWNLOAD_TYPES_COMPLETE)
            if input() == strings.PROMPT_YES:
                filetypes = list(set(filetypes))
                fileio.save_setting(strings.SETTING_UPDATE_FILETYPES, filetypes)
                return filetypes
