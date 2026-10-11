from contextlib import ExitStack
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import Mock, patch

from PIL import Image
import requests

from engine import Engine  # noqa: F401 - establishes the project's import order
from engine.file import cache as cache_module
from engine.file.cache import Cache
from engine.device.web.server.server_files import GameServerFiles


PRIMARY = 'https://cerebrodatastorage.blob.core.windows.net/cerebro-cards/official/{card_id:U}.jpg'
BACKUP = 'https://marvelcdb.com/bundles/cards/{card_id}.jpg'


def image_bytes(format='JPEG', color='blue'):
    output = BytesIO()
    Image.new('RGB', (8, 12), color).save(output, format=format)
    return output.getvalue()


def response(data, content_type='image/jpeg'):
    result = Mock()
    result.content = data
    result.headers = {'Content-Type': content_type}
    result.raise_for_status.return_value = None
    return result


class TestImageDownloadRecovery(unittest.TestCase):

    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        root = Path(self.stack.enter_context(tempfile.TemporaryDirectory()))
        self.cache = root / 'cache'
        self.cache.mkdir()
        self.now = 0
        self.art = image_bytes()
        self.placeholder = image_bytes(color='red')
        for name in ('cache', 'retry_after', 'host_retry_after', 'link_pic'):
            self.stack.enter_context(patch.object(Cache, name, {}))
        for variable, value in (
            (cache_module.IMAGE_FOLDERS, []),
            (cache_module.TEXTURE_FOLDER, str(root / 'textures')),
            (cache_module.CACHE_FOLDER, str(self.cache)),
            (cache_module.IMAGE_SERVERS, [PRIMARY, BACKUP]),
            (cache_module.SAVE_EMPTY_IMAGE, True),
            (cache_module.BREAK_WHEN_LOAD_ONLINE_IMAGE, False),
        ):
            self.stack.enter_context(patch.object(variable, 'value', value))
        self.stack.enter_context(patch.object(cache_module, 'monotonic', side_effect=lambda: self.now))
        self.stack.enter_context(patch.object(cache_module.ImageCreator, 'CreateNoImage', return_value=self.placeholder))
        self.stack.enter_context(patch.object(cache_module.Log, 'Warn'))
        self.stack.enter_context(patch.object(cache_module.Log, 'DebugInfo'))
        self.get = self.stack.enter_context(patch.object(cache_module.requests, 'get'))

    def test_timeout_falls_back_and_keeps_successful_artwork(self):
        self.get.side_effect = [requests.Timeout(), response(self.art)]

        self.assertEqual(Cache.LoadImage('37006'), self.art)
        self.assertEqual((self.cache / '37006.jpg').read_bytes(), self.art)
        self.assertEqual([call.args[0] for call in self.get.call_args_list], [
            PRIMARY.replace('{card_id:U}', '37006'),
            BACKUP.replace('{card_id}', '37006'),
        ])
        self.now = 300
        self.assertEqual(Cache.LoadImage('37006'), self.art)
        self.assertEqual(self.get.call_count, 2)

    def test_failed_placeholder_retries_after_cooldown_without_restarting(self):
        self.get.side_effect = [requests.Timeout(), requests.Timeout(), response(self.art)]

        self.assertEqual(Cache.LoadImage('37006'), self.placeholder)
        self.assertEqual(list(self.cache.iterdir()), [])
        self.now = Cache.RETRY_SECONDS - 1
        self.assertEqual(Cache.LoadImage('37006'), self.placeholder)
        self.assertEqual(self.get.call_count, 2)
        self.now = Cache.RETRY_SECONDS + 1
        self.assertEqual(Cache.LoadImage('37006'), self.art)
        self.assertEqual(self.get.call_count, 3)
        self.assertNotIn('37006', Cache.retry_after)

    def test_unreachable_host_is_skipped_for_other_cards_then_recovers(self):
        self.get.side_effect = [requests.ConnectionError('DNS lookup failed'), response(self.art), response(self.art), response(self.art)]

        self.assertEqual(Cache.LoadImage('37005'), self.art)
        self.assertEqual(Cache.LoadImage('37006'), self.art)
        urls = [call.args[0] for call in self.get.call_args_list]
        self.assertEqual(urls, [
            PRIMARY.replace('{card_id:U}', '37005'),
            BACKUP.replace('{card_id}', '37005'),
            BACKUP.replace('{card_id}', '37006'),
        ])
        self.now = Cache.RETRY_SECONDS + 1
        self.assertEqual(Cache.LoadImage('37007'), self.art)
        self.assertEqual(self.get.call_args.args[0], PRIMARY.replace('{card_id:U}', '37007'))
        self.assertEqual(Cache.host_retry_after, {})

    def test_missing_card_does_not_disable_a_working_provider(self):
        missing = requests.HTTPError(response=Mock(status_code=404))
        self.get.side_effect = [missing, response(self.art), response(self.art)]

        self.assertEqual(Cache.LoadImage('37005'), self.art)
        self.assertEqual(Cache.LoadImage('37006'), self.art)
        self.assertEqual(self.get.call_args.args[0], PRIMARY.replace('{card_id:U}', '37006'))

    def test_one_slow_image_does_not_disable_other_images_on_that_provider(self):
        self.get.side_effect = [requests.Timeout(), response(self.art), response(self.art)]

        self.assertEqual(Cache.LoadImage('37005'), self.art)
        self.assertEqual(Cache.LoadImage('37006'), self.art)
        self.assertEqual(self.get.call_args.args[0], PRIMARY.replace('{card_id:U}', '37006'))

    def test_service_failure_uses_the_host_cooldown(self):
        unavailable = requests.HTTPError(response=Mock(status_code=503))
        self.get.side_effect = [unavailable, response(self.art), response(self.art)]

        self.assertEqual(Cache.LoadImage('37005'), self.art)
        self.assertEqual(Cache.LoadImage('37006'), self.art)
        self.assertEqual(self.get.call_args.args[0], BACKUP.replace('{card_id}', '37006'))

    def test_invalid_response_is_not_saved_and_backup_can_succeed(self):
        self.get.side_effect = [response(b'<html>Service unavailable</html>', 'text/html'), response(self.art)]

        self.assertEqual(Cache.LoadImage('37006'), self.art)
        self.assertEqual((self.cache / '37006.jpg').read_bytes(), self.art)
        self.assertEqual(self.get.call_count, 2)

    def test_actual_image_format_wins_over_incorrect_content_type(self):
        png = image_bytes('PNG')
        self.get.return_value = response(png, 'image/jpeg')

        self.assertEqual(Cache.LoadImage('37006'), png)
        self.assertEqual((self.cache / '37006.png').read_bytes(), png)
        self.assertFalse((self.cache / '37006.jpg').exists())

    def test_copied_cache_works_without_either_image_provider(self):
        (self.cache / '37006.jpg').write_bytes(self.art)
        self.get.side_effect = requests.ConnectionError('Offline')

        self.assertEqual(Cache.LoadImage('37006'), self.art)
        self.get.assert_not_called()

    def test_corrupt_cache_file_can_be_downloaded_again(self):
        (self.cache / '37006.jpg').write_bytes(b'Interrupted download')
        self.get.return_value = response(self.art)

        self.assertEqual(Cache.LoadImage('37006'), self.art)
        self.assertEqual((self.cache / '37006.jpg').read_bytes(), self.art)
        self.assertEqual(self.get.call_count, 1)

    def test_temporary_response_signals_retry_and_disables_browser_cache(self):
        server = object.__new__(GameServerFiles)
        server.HeaderCache = {'Cache-Control': 'public, max-age=31536000'}
        server.device_manager = Mock()
        request = SimpleNamespace(path='/37007')
        self.get.side_effect = [requests.Timeout(), requests.Timeout(), response(self.art)]

        failed = server.handle_image_request(request)
        self.assertEqual(failed.status, 200)
        self.assertEqual(failed.body, self.placeholder)
        self.assertEqual(failed.headers['X-Card-Image-Retry-After'], '30')
        self.assertEqual(failed.headers['Cache-Control'], 'no-store')
        self.now = 17.2
        self.assertEqual(server.handle_image_request(request).headers['X-Card-Image-Retry-After'], '13')
        self.now = 31
        recovered = server.handle_image_request(request)
        self.assertEqual(recovered.body, self.art)
        self.assertNotIn('X-Card-Image-Retry-After', recovered.headers)
        self.assertEqual(recovered.headers['Cache-Control'], server.HeaderCache['Cache-Control'])

    def test_linked_image_reports_source_retry_until_recovered(self):
        Cache.SetLinkPic('alias', '37007')
        self.get.side_effect = [requests.Timeout(), requests.Timeout(), response(self.art)]
        self.assertEqual(Cache.LoadImage('alias'), self.placeholder)
        self.assertEqual(Cache.GetImageRetrySeconds('/alias'), 30)
        self.now = 31
        self.assertEqual(Cache.LoadImage('alias'), self.art)
        self.assertIsNone(Cache.GetImageRetrySeconds('alias'))

    def test_intentional_text_image_is_not_retried(self):
        Cache.LoadImage('no_image')
        self.assertIsNone(Cache.GetImageRetrySeconds('no_image'))
        self.get.assert_not_called()


if __name__ == '__main__':
    unittest.main()
