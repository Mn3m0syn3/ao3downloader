import unittest
import ao3downloader.strings as strings
from unittest.mock import MagicMock
from ao3downloader import *

class TestAo3(unittest.TestCase):
    def setUp(self) -> None:
        self.mockfileops = MagicMock(spec=FileOps)
        self.mocktextparse = MagicMock(spec=TextParse)
        self.mocksoupparse = MagicMock(spec=SoupParse)
        self.mockrepository = MagicMock(spec=Repository)
        self.ao3base = Ao3Base(self.mockfileops, self.mocktextparse, self.mocksoupparse, self.mockrepository)

    def getao3_worklinkstest(self, series: bool, pages: int = None) -> Ao3:
        return Ao3(self.ao3base, None, False, series, pages)

# region get_work_links

    def test_get_work_links_worklink_returnsworklink(self) -> None:

        # arrange
        ao3 = self.getao3_worklinkstest(False)

        # act
        links_list = ao3.get_work_links(strings.AO3_IDENTIFIER_WORK)

        # assert
        self.mockfileops.assert_not_called()
        self.mocktextparse.assert_not_called()
        self.mocksoupparse.assert_not_called()
        self.mockrepository.assert_not_called()

        self.assertEqual(1, len(links_list))
        self.assertEqual(strings.AO3_IDENTIFIER_WORK, links_list[0])

    def test_get_work_links_serieslink_noseries_returnsemptylist(self) -> None:

        # arrange
        ao3 = self.getao3_worklinkstest(False)

        # act
        links_list = ao3.get_work_links(strings.AO3_IDENTIFIER_SERIES)

        # assert
        self.mockfileops.assert_not_called()
        self.mocktextparse.assert_not_called()
        self.mocksoupparse.assert_not_called()
        self.mockrepository.assert_not_called()

        self.assertFalse(links_list)

    def test_get_work_links_serieslink_yesseries_notlocked_returnsworkurls(self) -> None:

        # arrange
        work_urls = [f'{strings.AO3_IDENTIFIER_WORK}123', f'{strings.AO3_IDENTIFIER_WORK}456']

        self.mocksoupparse.proceed.return_value = False
        self.mocksoupparse.get_work_urls.return_value = work_urls

        ao3 = self.getao3_worklinkstest(True)

        # act
        links_list = ao3.get_work_links(strings.AO3_IDENTIFIER_SERIES)

        # assert
        self.mockfileops.assert_not_called()
        self.mocktextparse.assert_not_called()

        self.mocksoupparse.proceed.assert_called_once()
        self.mocksoupparse.get_work_urls.assert_called_once()
        self.mockrepository.get_soup.assert_called_once()

        self.assertEqual(work_urls, links_list)

    def test_get_work_links_serieslink_yesseries_islocked_returnsworkurls(self) -> None:

        # arrange
        work_urls = [f'{strings.AO3_IDENTIFIER_WORK}123',f'{strings.AO3_IDENTIFIER_WORK}456']

        self.mocksoupparse.proceed.return_value = True
        self.mocksoupparse.get_work_urls.return_value = work_urls

        ao3 = self.getao3_worklinkstest(True)

        # act
        links_list = ao3.get_work_links(strings.AO3_IDENTIFIER_SERIES)

        # assert
        self.mockfileops.assert_not_called()
        self.mocktextparse.assert_not_called()

        self.mocksoupparse.proceed.assert_called_once()
        self.mocksoupparse.get_work_urls.assert_called_once()
        self.assertEqual(2, self.mockrepository.get_soup.call_count)

        self.assertEqual(work_urls, links_list)

    def test_get_work_links_ao3link_returnsworkurls(self) -> None:

        # arrange
        work_urls = [f'{strings.AO3_IDENTIFIER_WORK}123',f'{strings.AO3_IDENTIFIER_WORK}456']
        self.mocksoupparse.get_work_urls.return_value = work_urls

        ao3 = self.getao3_worklinkstest(False)

        # act
        links_list = ao3.get_work_links(strings.AO3_IDENTIFIER)

        # assert
        self.assertEqual(work_urls, links_list)

    def test_get_work_links_ao3link_duplicates_doesnotreturnduplicates(self) -> None:

        # arrange
        work_urls = [f'{strings.AO3_IDENTIFIER_WORK}123',f'{strings.AO3_IDENTIFIER_WORK}123']
        self.mocksoupparse.get_work_urls.return_value = work_urls

        ao3 = self.getao3_worklinkstest(False)

        # act
        links_list = ao3.get_work_links(strings.AO3_IDENTIFIER)

        # assert
        self.assertEqual(1, len(links_list))

    def test_get_work_links_ao3link_withseries_returnsallworkurls(self) -> None:

        # arrange
        page_urls = [
            f'{strings.AO3_IDENTIFIER_WORK}123',
            f'{strings.AO3_IDENTIFIER_WORK}456',
            f'{strings.AO3_IDENTIFIER_SERIES}789']
        series_works = [
            f'{strings.AO3_IDENTIFIER_WORK}321',
            f'{strings.AO3_IDENTIFIER_WORK}654']

        self.mocksoupparse.get_work_and_series_urls.return_value = page_urls
        self.mocksoupparse.get_work_urls.return_value = series_works

        ao3 = self.getao3_worklinkstest(True)

        # act
        links_list = ao3.get_work_links(strings.AO3_IDENTIFIER)

        # assert
        self.assertEqual(4, len(links_list))

    def test_get_work_links_ao3link_pages(self) -> None:

        # arrange
        work_urls = [f'{strings.AO3_IDENTIFIER_WORK}123']

        self.mocksoupparse.get_work_urls.return_value = work_urls
        self.mocktextparse.get_page_number.return_value = 2

        ao3 = self.getao3_worklinkstest(False, 1)

        # act
        ao3.get_work_links(strings.AO3_IDENTIFIER)

        # assert
        self.mocktextparse.get_page_number.assert_called_once()

# endregion
