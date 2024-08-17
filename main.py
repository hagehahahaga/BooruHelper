import functools
import pathlib
import itertools
import json
import pickle
import queue
import threading
import time
import os
import shutil
import urllib.parse
import selenium.webdriver


def error_handler(func):
    @functools.wraps(func)
    def decorated(*args, **kwargs):
        for i in range(5):
            try:
                return func(*args, *kwargs)
            except Exception as error:
                error = error
                continue
        else:
            raise error

    return decorated


class WebManager:
    class Tab:
        def __init__(
                self,
                explorer: selenium.webdriver.Chrome,
                explorer_lock: threading.Lock,
                window_handle: str = None
        ):
            self.explorer = explorer
            self.explorer_lock = explorer_lock
            if window_handle:
                self.handle = window_handle
                return
            original_handle = self.explorer.current_window_handle
            self.explorer.switch_to.new_window()
            self.handle = self.explorer.current_window_handle
            self.explorer.switch_to.window(original_handle)

        def __enter__(self):
            self.explorer_lock.acquire()
            self.original_handle = self.explorer.current_window_handle
            self.explorer.switch_to.window(self.handle)

        def __exit__(self, exc_type, exc_val, exc_tb):
            self.explorer_lock.release()
            self.explorer.switch_to.window(self.original_handle)

        def __del__(self):
            with self:
                self.explorer.switch_to.window(self.handle)
                self.explorer.close()

        @error_handler
        def get_text(self) -> str:
            with self:
                return self.explorer.find_element(
                    selenium.webdriver.common.by.By.XPATH,
                    '/*'
                ).text

        @error_handler
        def get_json(self):
            return json.loads(self.get_text())

        @error_handler
        def get_url(self) -> str:
            with self:
                return self.explorer.current_url

        @error_handler
        def goto(self, url: str | list[str, dict]):
            with self:
                self.explorer.get(url)
            return self

    def __init__(self):
        self.explorer_control_lock = threading.Lock()

        self.option = selenium.webdriver.ChromeOptions()
        self.option.binary_location = r'D:\Chrome\Application\chrome.exe'
        self.option.enable_downloads = True
        prefs = {
            "download.default_directory": r'C:\Users\Administrator.DESKTOP-MQIAPM5\Documents\GitHub\pythonProject\images',
            'profile.default_content_settings.popups': 0,
            "profile.default_content_setting_values.automatic_downloads": 1
        }
        self.option.add_experimental_option('prefs', prefs)
        self.explorer = selenium.webdriver.Chrome(options=self.option)

        self.current_tab = self.Tab(explorer=self.explorer, explorer_lock=self.explorer_control_lock,
                                    window_handle=self.explorer.current_window_handle)
        self.tabs = [
            self.current_tab
        ]

    def get_json(self, url: str = None) -> dict:
        if url:
            return self.Tab(explorer=self.explorer, explorer_lock=self.explorer_control_lock).goto(url).get_json()
        else:
            return self.current_tab.get_json()

    def focus(self, tab: Tab):
        with self.explorer_control_lock:
            self.current_tab = tab
            self.explorer.switch_to.window(self.current_tab.handle)


class DownloadManager(WebManager):
    class Tab(WebManager.Tab):
        def download(self):
            url = self.get_url()
            url_name = urllib.parse.unquote(url.split('/')[-1])
            with self:
                self.explorer.execute_script(
                    f'fetch("{url}").then('
                    '(res) => {'
                    'res.blob().then('
                    '(blob) => {'
                    'const blobUrl = window.URL.createObjectURL(blob);'
                    'const a = document.createElement("a");'
                    'a.href = blobUrl;'
                    f'a.download = "{url_name}";'
                    'a.click();'
                    'window.URL.revokeObjectURL(blobUrl)'
                    '}'
                    ')'
                    '}'
                    ')'
                )
                time.sleep(0.5)

    def __init__(self, download_queue: list = None):
        WebManager.__init__(self)
        self.queue = queue.Queue()
        if download_queue:
            for item in download_queue:
                self.queue.put(item)
        threading.Thread(target=self.downloader).start()

    def download(self, url: str):
        self.queue.put(url)
        data["download_queue"] = list(self.queue.queue)

    def downloader(self):
        while True:
            url = self.queue.get()
            self.current_tab.goto(url).download()
            data["download_queue"] = list(self.queue.queue)


class Data:
    def __init__(self, path: pathlib.Path) -> None:
        self.path = path
        self.data = pickle.loads(path.read_bytes())
        self.control_lock = threading.Lock()

    def __getitem__(self, key):
        return self.data[key]

    def __setitem__(self, key, value):
        self.data[key] = value
        self.save()

    def __delitem__(self, key):
        del self.data[key]
        self.save()

    def save(self):
        with self.control_lock:
            self.path.write_bytes(
                pickle.dumps(
                    self.data
                )
            )


def page_iterator(tags: tuple) -> dict:
    num = 50
    if tags not in data['cache']:
        data['cache'][tags] = {}
        data['cache'][tags]['searched'] = False
        data['cache'][tags]['cache'] = []
    for page in itertools.count():
        response = browser.get_json(
            f'{url_base}{urllib.parse.urlencode({"limit": num, "tags": " ".join(tags), "page": page})}'
        )
        if not response:
            return
        for image in response:
            if image['id'] in data['cache'][tags]['cache']:
                if data['cache'][tags]['searched']:
                    return
                continue
            yield image
            data['cache'][tags]['cache'].append(image['id'])
        if len(response) < num:
            data['cache'][tags]['searched'] = True
            return


def main():
    dislike_times = 0
    tags_old = [None]
    reset = False
    completed_tags = []
    while True:
        tag_num: int = data['tag_num']
        sorted_tags = get_sorted_tags()

        for tags in filter(
                lambda a: a not in completed_tags,
                map(
                    lambda b: tuple(
                        sorted_tags[b:b + tag_num]
                    ),
                    range(
                        len(sorted_tags) - tag_num
                    )
                )
        ) if tag_num > 0 else [()]:  # choose tags

            if tags != tags_old:
                print('\ntags:\n')
                print('\n'.join(tags), '\n')
                tags_old = tags

            for response in filter(
                    lambda a: a['id'] not in itertools.chain(
                        local_files,
                        data['disliked_ids']
                    ),
                    page_iterator(tags)
            ):  # get responses
                browser.explorer.get(response['sample_url'])
                response_tags = response['tags'].split(' ')
                for tag in response_tags:
                    if tag not in data['tag_values']:
                        data['tag_values'][tag] = 0

                if input('Like this? Enter for false.'):
                    dislike_times = 0

                    for tag in response_tags:
                        data['tag_values'][tag] += 1

                    downloader.download(response['file_url'])
                    local_files.add(response['id'])

                    if tag_num < 6:
                        data['tag_num'] += 1
                else:
                    data["disliked_ids"].append(response['id'])
                    for tag in tags:
                        data['tag_values'][tag] -= 0.1 * dislike_times ** 1.5
                    for tag in response_tags:
                        data['tag_values'][tag] -= 0.1
                    dislike_times += 1

                data.save()
                if get_sorted_tags() != sorted_tags or tag_num != data['tag_num']:
                    reset = True
                    break
            else:
                completed_tags.append(tags)
            if reset:
                break
        else:
            if data['tag_num'] > 0:
                data['tag_num'] -= 1


def get_sorted_tags():
    return sorted(
        data['tag_values'].keys(),
        key=lambda a: data['tag_values'][a],
        reverse=True
    )


url_base = f'https://yande.re/post.json?'
if __name__ == '__main__':
    shutil.copy('data.pickle', f'./data_backup/{time.strftime("%Y%m%d %H%M%S", time.gmtime())}.bak')
    data = Data(pathlib.Path('data.pickle'))
    browser = WebManager()
    downloader = DownloadManager(data["download_queue"])

    local_files = set(
        map(
            lambda a: int(
                a.split(' ')[1]
            ),
            filter(
                lambda a: a.startswith('yande.re'),
                itertools.chain(
                    *map(
                        lambda a: next(os.walk(a))[2],
                        (
                            r"E:\H\images\2",
                            'C:/Users/Administrator.DESKTOP-MQIAPM5/Desktop/待分类',
                            './images'
                        )
                    ),
                    map(
                        lambda a: urllib.parse.unquote(
                            a.split('/')[-1]
                        ),
                        data["download_queue"]
                    )
                )
            )
        )
    )

    main()
