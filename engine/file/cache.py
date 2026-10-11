from core import *
import requests
from time import monotonic
from urllib.parse import urlsplit
from engine.lib import ImageCreator, ImageLib
from engine.log import Log
from engine.file import FileManager
from engine.config import ConfigVariables

CATEGORY_NAME = "CACHE"

IMAGE_FOLDERS   = ConfigVariables.Folders('image_folders', ["./assets/pics/"])
TEXTURE_FOLDER  = ConfigVariables.Folder('texture_folder', "./assets/textures/")
CACHE_FOLDER    = ConfigVariables.Folder('cache_folder', "./assets/cache/")
IMAGE_SERVERS   = ConfigVariables.ListStr('image_servers', [])
SAVE_EMPTY_IMAGE = ConfigVariables.Bool('save_empty_image', True)
BREAK_WHEN_LOAD_ONLINE_IMAGE = ConfigVariables.Bool('break_when_load_online_image', False)

class Cache:

    cache: Dict[str, bytes] = {}
    link_pic: Dict[str, str] = {}
    # A failed download must not make a placeholder permanent for this session.
    retry_after: Dict[str, float] = {}
    host_retry_after: Dict[str, float] = {}
    RETRY_SECONDS = 30
    DOWNLOAD_TIMEOUT = (5, 10)  # Connection and response-body timeouts.

    # Scenario reference cards are not exposed by the numbered card-image
    # providers. Keep their official image locations explicit so they use the
    # same on-disk cache and offline fallback as every other card image.
    SPECIAL_IMAGE_URLS: Dict[str, str] = {
        "shatter_the_illusion": "https://hallofheroeslcg.com/wp-content/uploads/2025/08/shattertheillusion.jpg",
    }

    # These physical cards use Alter-Ego A / Hero B numbering. MarvelCDB
    # normalizes their images to Hero A / Alter-Ego B to match the card data,
    # while Cerebro retains the physical side letters.
    CEREBRO_REVERSED_IDENTITY_SIDES: Dict[str, str] = {
        "16001a": "16001b", "16001b": "16001a",  # Groot
        "16029a": "16029b", "16029b": "16029a",  # Rocket Raccoon
        "32001a": "32001b", "32001b": "32001a",  # Colossus
        "32030a": "32030b", "32030b": "32030a",  # Shadowcat
        "33001a": "33001b", "33001b": "33001a",  # Cyclops
        "34001a": "34001b", "34001b": "34001a",  # Phoenix
        "35001a": "35001b", "35001b": "35001a",  # Wolverine
        "36001a": "36001b", "36001b": "36001a",  # Storm
        "37001a": "37001b", "37001b": "37001a",  # Gambit
        "38001a": "38001b", "38001b": "38001a",  # Rogue
    }

    @staticmethod
    def GetCacheFileName(card_id: str) -> str:
        if card_id in Cache.CEREBRO_REVERSED_IDENTITY_SIDES:
            # Do not reuse files downloaded before the provider-side mapping
            # was corrected. Those files may contain the opposite face.
            return f"normalized-identity-sides/{card_id}"
        return card_id

    @staticmethod
    def GetRemoteCardId(site: str, card_id: str) -> str:
        if "cerebrodatastorage.blob.core.windows.net" in site:
            return Cache.CEREBRO_REVERSED_IDENTITY_SIDES.get(card_id, card_id)
        return card_id

    @staticmethod
    def SetLinkPic(card_id: str, link_to_pic_id: str):
        Cache.link_pic[card_id] = link_to_pic_id

    @staticmethod
    def SetCache(card_id: str, data: bytes):
        Cache.cache[card_id] = data
        Cache.retry_after.pop(card_id, None)

    @staticmethod
    def LoadImage(card_id: str) -> bytes:
        # if url in ['enthralled_minion', 'minion', 'ultron_facedown_drone']:
        #     url = 'player'
        card_id = card_id.lstrip("/")

        if card_id in Cache.cache:
            if monotonic() < Cache.retry_after.get(card_id, float('inf')):
                return Cache.cache[card_id]
            Cache.cache.pop(card_id, None)
            Cache.retry_after.pop(card_id, None)

        assert card_id != "", f"{card_id=}"
        file_name = card_id

        check_folders = IMAGE_FOLDERS.value + [TEXTURE_FOLDER.value]
        cache_file_name = Cache.GetCacheFileName(file_name)

        def try_load_image_data(image_data: bytes):
            return ImageLib.TryRotateImage(image_data)

        # Load the image from the cache and images
        def try_load_image_path(file_path: str) -> bytes|None:
            for ext_name in [".webp", ".jpg", ".png"]:
                check_path = file_path + ext_name
                if FileManager.Exists(check_path):
                    try:
                        with FileManager.OpenFile(check_path, read=True, bin=True) as file:
                            return try_load_image_data(file.Read())
                    except (OSError, ValueError) as error:
                        Log.Warn(CATEGORY_NAME, f"Invalid cached image {check_path}: {error}")
            return None

        def try_load_image_name(name: str) -> bytes|None:
            for cache_folder in check_folders:
                file_paths: List[str] = []
                file_paths.append(f"{cache_folder}/{name}")
                for file_path in file_paths:
                    image_data = try_load_image_path(file_path)
                    if image_data:
                        return image_data
            return None

        image_data = try_load_image_name(file_name)
        if image_data:
            Cache.SetCache(file_name, image_data)
            return image_data

        image_data = try_load_image_path(
            FileManager.JoinPath(CACHE_FOLDER.value, cache_file_name)
        )
        if image_data:
            Cache.SetCache(file_name, image_data)
            return image_data

        if file_name in Cache.link_pic:
            image_data = Cache.LoadImage(Cache.link_pic[file_name])
            if image_data:
                return image_data

        def check_is_card_id(s: str):
            import re
            # Pattern to match: four digits followed by a lowercase letter
            pattern = r'^\d{5}[a-z]?$'
            return re.match(pattern, s)

        def save_to_file(file_name: str, ext_name: str, data: bytes):
            file_path = FileManager.JoinPath(CACHE_FOLDER.value, f"{file_name}.{ext_name}")
            FileManager.MakeDir(FileManager.GetDirName(file_path))
            with FileManager.OpenFile(file_path, write=True, bin=True) as file:
                file.Write(data)

        remote_urls: List[str] = []
        if card_id in Cache.SPECIAL_IMAGE_URLS:
            remote_urls.append(Cache.SPECIAL_IMAGE_URLS[card_id])
        elif IMAGE_SERVERS.value and check_is_card_id(card_id):
            for site in IMAGE_SERVERS.value:
                remote_card_id = Cache.GetRemoteCardId(site, card_id)
                full_url = site.replace('{card_id}', remote_card_id)
                full_url = full_url.replace('{card_id:U}', remote_card_id.upper())
                remote_urls.append(full_url)

        if remote_urls:
            # Load the image from the internet
            skip_break = not BREAK_WHEN_LOAD_ONLINE_IMAGE.value
            if not skip_break:
                Debug.DebugBreak()

            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3'
            }

            # "https://cerebrodatastorage.blob.core.windows.net/cerebro-cards/official/${card_id}.jpg",
            # "https://marvelcdb.com/bundles/cards/${card_id}.jpg",
            # "https://marvelcdb.com/bundles/cards/${card_id}.png",

            for full_url in remote_urls:
                host = urlsplit(full_url).netloc
                if monotonic() < Cache.host_retry_after.get(host, 0):
                    continue
                try:
                    Log.DebugInfo(CATEGORY_NAME, f"Downloading from {full_url}")

                    response = requests.get(full_url, headers=headers, timeout=Cache.DOWNLOAD_TIMEOUT)
                    response.raise_for_status()
                    data = response.content
                    try:
                        image_data = try_load_image_data(data)
                    except (OSError, ValueError) as error:
                        Log.Warn(CATEGORY_NAME, f"Invalid image downloaded from {full_url}: {error}")
                        continue
                    # Some providers label PNG bytes as JPEG, or vice versa.
                    ext_name = {
                        'image/jpeg': 'jpg',
                        'image/png': 'png',
                        'image/webp': 'webp',
                    }[ImageLib.GetContentType(data)]
                    save_to_file(cache_file_name, ext_name, data)
                    Log.DebugInfo(CATEGORY_NAME, f"Downloaded: {file_name}")
                    Cache.host_retry_after.pop(host, None)
                    Cache.SetCache(file_name, image_data)
                    return image_data
                except requests.exceptions.Timeout:
                    Log.Warn(CATEGORY_NAME, f"Timeout occurred while downloading {file_name}")
                except requests.exceptions.RequestException as e:
                    Log.Warn(CATEGORY_NAME, f"Request failed with error: {e}")
                    if isinstance(e, requests.exceptions.ConnectionError) or (
                        e.response is not None and (e.response.status_code == 429 or e.response.status_code >= 500)
                    ):
                        Cache.host_retry_after[host] = monotonic() + Cache.RETRY_SECONDS

        # raise Exception(f"Failed to load {file_name} from the internet")
        image_data = ImageCreator.CreateNoImage(
            card_id,
            force_text=card_id in Cache.SPECIAL_IMAGE_URLS,
        )
        # Never write failed remote downloads as artwork: they must be able to
        # recover when the provider or connection returns.
        if SAVE_EMPTY_IMAGE.value and not remote_urls:
            save_to_file(cache_file_name, "jpg", image_data)
        Cache.SetCache(file_name, image_data)
        if remote_urls:
            Cache.retry_after[file_name] = monotonic() + Cache.RETRY_SECONDS
        return image_data
