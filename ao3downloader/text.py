INVALID_FILENAME_CHARACTERS = '<>:"/\|?*.' + ''.join(chr(i) for i in range(32))


def get_valid_filename(filename: str) -> str:
    valid_name = filename.translate({ord(i):None for i in INVALID_FILENAME_CHARACTERS})
    return valid_name[:100].strip()


def get_file_type(filetype: str) -> str:
    return '.' + filetype.lower()


def get_next_page(link: str) -> str:
    index = str.find(link, 'page=')
    if index == -1:
        if str.find(link, '?') == -1:
            newlink = link + '?page=2'
        else:
            newlink = link + '&page=2'
    else:
        i = index + 5
        page = get_num_from_link(link, i)
        nextpage = int(page) + 1
        newlink = link.replace('page=' + page, 'page=' + str(nextpage))
    return newlink


def get_page_number(link: str) -> int:
    index = str.find(link, 'page=')
    if index == -1:
        return 1
    else:
        i = index + 5
        page = get_num_from_link(link, i)
        return int(page)


def get_num_from_link(link: str, index: int) -> str:
    end = index + 1
    while end < len(link) and str.isdigit(link[index:end+1]):
        end = end + 1
    return link[index:end]


def get_total_chapters(text: str, index: int) -> str:
    '''read characters after index until encountering a space.'''
    totalchap = ''
    for c in text[index+1:]:
        if c.isspace():
            break
        else:
            totalchap += c
    return totalchap


def get_current_chapters(text: str, index: int) -> str:
    ''' 
    reverse text before index, then read characters from beginning of reversed text 
    until encountering a space, then un-reverse the value you got. 
    we assume here that the text does not include unicode values.
    this should be safe because ao3 doesn't have localization... I think.
    '''
    currentchap = ''
    for c in reversed(text[:index]):
        if c.isspace():
            break
        else:
            currentchap += c
    currentchap = currentchap[::-1]
    return currentchap
