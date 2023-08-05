import copy
import itertools
import json
import pickle
import threading
import time
import requests
import os
import shutil
import pychrome
import urllib.parse


class Data:
    def __init__(self, data: dict) -> None:
        self.data = data

    def __getitem__(self, key):
        return self.data[key]

    def __setitem__(self, key, value):
        self.data[key] = value
        self.save()

    def __delitem__(self, key):
        del self.data[key]
        self.save()

    def save(self):
        with open('data.pickle', mode='wb') as data_file:
            pickle.dump(pickle.dumps(self.data), data_file)


class Tab:
    def __init__(self, parent: pychrome.Tab):
        self.tab = parent

    def __enter__(self):
        self.tab.start()
        self.tab.Network.enable()
        return self.tab

    def __exit__(self, exc_type, exc_val, exc_tb):
        pychrome.Browser().close_tab(self.tab)


def url_get(url: str) -> list[dict] | requests.Response:
    """return dict?"json" is in url:response"""
    times = 0
    while True:
        if times != 0:
            print(f'URL:{url}')
            input('Press enter to retry.')
        times += 1

        with open('headers.json') as file:
            data = json.load(file)
            cookies = data['cookies']
            headers = data['headers']
        response = None

        try:
            response = requests.get(
                url=url,
                headers=headers,
                cookies=cookies
            )
        except requests.exceptions.ConnectTimeout:
            input(f'Web error: Connect timeout.')
            continue
        except requests.exceptions.ConnectionError as exception:
            input(f'Web error: {exception}.')
            continue

        if response.status_code != 200:
            input(f'Web error: {response.status_code}.')
            continue

        if response.text.startswith('<'):
            input('Anti robot blocked, change headers.json.')
            continue

        if 'json' in url:
            response = json.loads(response.text)

        break

    return response


def page_iterator(tag: list) -> dict:
    url = f'{url_base}limit=100&tags={"+".join(tag)}&page='
    page = 1
    while True:
        response = url_get(url + str(page))
        if not response:
            raise StopIteration
        for image in response:
            yield image
        if len(response) < 100:
            raise StopIteration

        page += 1


def downloader():
    while True:
        url = None
        try:
            url = data["down_lists"][0]
        except IndexError:
            time.sleep(5)
            continue

        while True:
            with open('headers.json') as file:
                json_data = json.load(file)
                cookies = json_data['cookies']
                headers = json_data['headers']

            response = None
            try:
                response = requests.get(
                    url=url,
                    headers=headers,
                    cookies=cookies
                )
            except requests.exceptions.ConnectTimeout:
                time.sleep(1)
                continue
            except requests.exceptions.ConnectionError:
                continue

            if response.status_code != 200:
                time.sleep(3)
                continue

            with open(f'./images/{urllib.parse.unquote(url.split("/")[-1])}', mode='wb') as file:
                file.write(response.content)
            data["down_lists"].remove(url)
            break


def main():
    threading.Thread(target=downloader).start()
    dislike_times = 0
    tags_old = []
    responses = iter([])
    while True:
        data.save()
        tags = sorted(
            data['tag_values'].keys(),
            key=lambda a: data['tag_values'][a],
            reverse=True
        )[:data['tag_num']]

        if tags != tags_old:
            print('\ntags:\n')
            print('\n'.join(tags), '\n')

            dislike_times = 0
            responses = filter(
                lambda a: a['id'] not in local_files and
                a['id'] not in data['disliked_ids'],
                page_iterator(tags)
            )
            tags_old = tags

        try:
            response = next(responses)
        except RuntimeError:
            data['tag_num'] -= 1
            continue

        tab.Page.navigate(url=(response['sample_url']))
        if input('Like this? Enter for false.'):
            dislike_times = 0
            if data['tag_num'] < 6:
                data['tag_num'] += 1

            for tag in response['tags'].split(' '):
                if tag not in data['tag_values']:
                    data['tag_values'][tag] = 0
                data['tag_values'][tag] += 1

            data["down_lists"].append(response['file_url'])
            local_files.add(response['id'])

            continue

        data["disliked_ids"].append(response['id'])
        for tag in tags:
            data['tag_values'][tag] -= 0.1 * dislike_times ** 1.5
        dislike_times += 1


url_base = 'https://konachan.com/post.json?'
if __name__ == '__main__':
    shutil.copy('data.pickle', f'./data_backup/{time.strftime("%Y%m%d %H%M%S", time.gmtime())}.bak')
    with open('data.pickle', mode='rb') as data_file:
        data = Data(pickle.loads(pickle.load(data_file)))

    local_files = set(
        map(
            lambda a: int(
                a.split(' ')[2]
            ),
            filter(
                lambda a: a.startswith('Konachan.com - '),
                itertools.chain(
                    itertools.chain.from_iterable(
                        map(
                            lambda a: next(os.walk(a))[2],
                            (
                                'E:/yellow/images/二赤原',
                                'C:/Users/Administrator.DESKTOP-MQIAPM5/Desktop/待分类',
                                './images'
                            )
                        )
                    ),
                    data["down_lists"]
                )
            )
        )
    )

    with Tab(pychrome.Browser().new_tab()) as tab:
        main()
