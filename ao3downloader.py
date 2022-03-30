import ao3downloader.strings as strings
from ao3downloader import Actions

def ao3_download_action():
    with Actions() as a:
        a.action_ao3()

def links_only_action():
    with Actions() as a:
        a.action_getlinks()

def update_epubs_action():
    with Actions() as a:
        a.action_update()

def update_series_action():
    with Actions() as a:
        a.action_updateseries
    
def re_download_action():
    with Actions() as a:
        a.action_redownload()

def pinboard_download_action():
    with Actions() as a:
        a.action_pinboard()

def log_visualization_action():
    with Actions() as a:
        a.action_logvisualization()

def display_menu():
    print(strings.PROMPT_OPTIONS)
    for key, value in actions.items():
        try:
            desc = value.description
        except AttributeError:
            desc = value.__name__
        print(' {}: {}'.format(key, desc))

def choose(choice):
    try:
        function = actions[choice]
        try:
            function()
        except Exception as e:
            print(str(e))
    except KeyError as e:
        print(strings.PROMPT_INVALID_ACTION)

display_menu.description = strings.ACTION_DESCRIPTION_DISPLAY_MENU
ao3_download_action.description = strings.ACTION_DESCRIPTION_AO3
update_epubs_action.description = strings.ACTION_DESCRIPTION_UPDATE
pinboard_download_action.description = strings.ACTION_DESCRIPTION_PINBOARD
log_visualization_action.description = strings.ACTION_DESCRIPTION_VISUALIZATION
re_download_action.description = strings.ACTION_DESCRIPTION_REDOWNLOAD
update_series_action.description = strings.ACTION_DESCRIPTION_UPDATE_SERIES
links_only_action.description = strings.ACTION_DESCRIPTION_LINKS_ONLY

QUIT_ACTION = 'q'
MENU_ACTION = 'd'

actions = {
    MENU_ACTION: display_menu,
    'a': ao3_download_action,
    'l': links_only_action,
    'u': update_epubs_action,
    's': update_series_action,
    'r': re_download_action,
    'p': pinboard_download_action,
    'v': log_visualization_action
    }

display_menu()

while True:
    print('\'{}\' to display the menu again'.format(MENU_ACTION))
    print('please enter your choice, or \'{}\' to quit:'.format(QUIT_ACTION))
    choice = input()
    if choice == QUIT_ACTION: break
    choose(choice)
