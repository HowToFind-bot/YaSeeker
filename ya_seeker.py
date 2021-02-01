#!/usr/bin/env python3
import sys

import requests
from socid_extractor import extract, parse_cookies

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/74.0.3729.169 Safari/537.36',
}

COOKIES_STR = ''


class IdTypeInfoAggregator:
    def __init__(self, identifier: str):
        if not self.validate_id(identifier):
            raise ValueError
        self.identifier = identifier
        self.info = {}
        self.sites_results = {}

    def validate_id(self, identifier):
        # TODO: id validation
        return True

    def aggregate(self, info: dict):
        for k, v in info.items():
            if k in self.info:
                if isinstance(self.info[k], set):
                    self.info[k].add(v)
                else:
                    self.info[k] = {self.info[k], v}
            else:
                self.info[k] = v

    def simple_get_info_request(self, url: str, headers_updates: dict={}, orig_url: str=None) -> dict:
        headers = dict(HEADERS)
        headers.update(headers_updates)
        r = requests.get(url, headers=headers, cookies=parse_cookies(COOKIES_STR))
        if 'enter_captcha_value' in r.text:
            info = {'Error': 'Captcha detected'}
        else:
            info = extract(r.text)
            if info:
                info['URL'] = orig_url or url
        return info

    def collect(self):
        for f in self.__dir__():
            if f.startswith('get_'):
                info = getattr(self, f)()
                self.sites_results[f.split('_')[1]] = info
                self.aggregate(info)

    def print(self):
        for sitename, data in self.sites_results.items():
            print('Yandex.' + sitename.capitalize())
            if not data:
                print('\tNot found.\n')
                continue

            if 'URL' in data:
                print(f'\tURL: {data.get("URL")}')
            for k, v in data.items():
                if k != 'URL':
                    print('\t' + k.capitalize() + ': ' + v)
            print()


class YaUsername(IdTypeInfoAggregator):
    def get_collections_info(self) -> dict:
        return self.simple_get_info_request(
            url=f'https://yandex.ru/collections/api/users/{self.identifier}',
            orig_url=f'https://yandex.ru/collections/user/{self.identifier}/'
        )

    def get_music_info(self) -> dict:
        orig_url = f'https://music.yandex.ru/users/{self.identifier}/playlists'
        referer = {'referer': orig_url}
        return self.simple_get_info_request(
            url=f'https://music.yandex.ru/handlers/library.jsx?owner={self.identifier}',
            orig_url=orig_url,
            headers_updates=referer,
        )

    def get_bugbounty_info(self) -> dict:
        return self.simple_get_info_request(f'https://yandex.ru/bugbounty/researchers/{self.identifier}/')


class YaPublicUserId(IdTypeInfoAggregator):
    def get_reviews_info(self) -> dict:
        return self.simple_get_info_request(f'https://reviews.yandex.ru/user/{self.identifier}')

    def get_znatoki_info(self) -> dict:
        return self.simple_get_info_request(f'https://yandex.ru/q/profile/{self.identifier}/')

    def get_zen_info(self) -> dict:
        return self.simple_get_info_request(f'https://zen.yandex.ru/user/{self.identifier}')

    def get_market_info(self) -> dict:
        return self.simple_get_info_request(f'https://market.yandex.ru/user/{self.identifier}/reviews')


def main():
    if len(sys.argv) > 1:
        username = sys.argv[1]
    else:
        username = input('Enter Yandex username / login / email: ')

    username = username.split('@')[0]
    print(f'Get info about {username}...')

    username_obj = YaUsername(username)
    username_obj.collect()
    username_obj.print()

    public_id = username_obj.info.get('yandex_public_id')

    if public_id:
        public_id_obj = YaPublicUserId(public_id)
        public_id_obj.collect()
        public_id_obj.print()


if __name__ == '__main__':
    main()
