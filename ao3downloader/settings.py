import ao3downloader.strings as strings
from ao3downloader.fileio import FileOps

class Settings:
    def __init__(self, fileio: FileOps):
        self.fileio = fileio

    def api_token(self):
        return self.fileio.setting(
            strings.PINBOARD_PROMPT_API_TOKEN, 
            strings.SETTING_API_TOKEN)

    def username(self):
        return self.fileio.setting(
            strings.AO3_PROMPT_USERNAME,
            strings.SETTING_USERNAME)

    def password(self):
        return self.fileio.setting(
            strings.AO3_PROMPT_PASSWORD,
            strings.SETTING_PASSWORD)

    def sleep_time(self) -> int:
        value = self.fileio.get_setting(strings.SETTING_SLEEP_TIME)
        return int(value) if value else strings.DEFAULT_SLEEP_TIME

    def set_sleep_time(self):
        print(strings.PROMPT_SLEEP_TIME)
        value = input()
        try:
            value = int(value)
            if value < 1: value = 1
        except:
            value = 1
        self.fileio.save_setting(strings.SETTING_SLEEP_TIME, value)

    def save_secrets(self):
        value = self.fileio.get_setting(strings.SETTING_SAVE_SECRETS)
        return bool(value) if value else strings.DEFAULT_SAVE_SECRETS

    def set_save_secrets(self):
        print(strings.PROMPT_SAVE_SECRETS)
        value = True if input() == strings.PROMPT_YES else False
        self.fileio.save_setting(strings.SETTING_SAVE_SECRETS, value)

    def update_folder(self):
        return self.fileio.setting(
            strings.UPDATE_PROMPT_INPUT,
            strings.SETTING_UPDATE_FOLDER)
    
    def download_types(self):
        filetypes = self.fileio.get_setting(strings.SETTING_FILETYPES)
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
                self.fileio.save_setting(strings.SETTING_FILETYPES, filetypes)
                return filetypes

    def update_types(self):
        filetypes = self.fileio.get_setting(strings.SETTING_UPDATE_FILETYPES)
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
                self.fileio.save_setting(strings.SETTING_UPDATE_FILETYPES, filetypes)
                return filetypes
