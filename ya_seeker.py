#!/usr/bin/env python3
import json
import os
import sys
from http.cookiejar import MozillaCookieJar

import requests
from socid_extractor import extract

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/74.0.3729.169 Safari/537.36',
}

COOKIES_FILENAME = 'cookies.txt'


def load_cookies(filename):
    cookies = {}
    if os.path.exists(filename):
        cookies_obj = MozillaCookieJar(filename)
        cookies_obj.load(ignore_discard=False, ignore_expires=False)

        for domain in cookies_obj._cookies.values():
            for cookie_dict in list(domain.values()):
                for _, cookie in cookie_dict.items():
                    cookies[cookie.name] = cookie.value

    return cookies


class IdTypeInfoAggregator:
    acceptable_fields = ()

    def __init__(self, identifier: str, cookies: dict):
        self.identifier = identifier
        self.cookies = cookies
        self.info = {}
        self.sites_results = {}

    @classmethod
    def validate_id(cls, name, identifier):
        return name in cls.acceptable_fields

    def aggregate(self, info: dict):
        for k, v in info.items():
            if k in self.info:
                if isinstance(self.info[k], set):
                    self.info[k].add(v)
                else:
                    self.info[k] = {self.info[k], v}
            else:
                self.info[k] = v

    def simple_get_info_request(self, url: str, headers_updates: dict = {}, orig_url: str = None) -> dict:
        headers = dict(HEADERS)
        headers.update(headers_updates)
        r = requests.get(url, headers=headers, cookies=self.cookies)
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
            print('[+] Yandex.' + sitename.capitalize())
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
    acceptable_fields = ('username',)

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

    def get_messenger_info(self) -> dict:
        url = 'https://yandex.ru/messenger/api/registry/api/'
        data = {"method": "search",
                "params": {"query": self.identifier, "limit": 10, "entities": ["messages", "users_and_chats"]}}
        r = requests.post(url, headers=HEADERS, cookies=self.cookies, files={'request': (None, json.dumps(data))})
        info = extract(r.text)
        if info and info.get('yandex_messenger_guid'):
            info['URL'] = f'https://yandex.ru/chat#/user/{info["yandex_messenger_guid"]}'
        return info


class YaPublicUserId(IdTypeInfoAggregator):
    acceptable_fields = ('yandex_public_id', 'id',)

    @classmethod
    def validate_id(cls, name, identifier):
        return len(identifier) == 26 and name in cls.acceptable_fields

    def get_reviews_info(self) -> dict:
        return self.simple_get_info_request(f'https://reviews.yandex.ru/user/{self.identifier}')

    def get_znatoki_info(self) -> dict:
        return self.simple_get_info_request(f'https://yandex.ru/q/profile/{self.identifier}/')

    def get_zen_info(self) -> dict:
        return self.simple_get_info_request(f'https://zen.yandex.ru/user/{self.identifier}')

    def get_market_info(self) -> dict:
        return self.simple_get_info_request(f'https://market.yandex.ru/user/{self.identifier}/reviews')


class YaMessengerGuid(IdTypeInfoAggregator):
    acceptable_fields = ('yandex_messenger_guid',)

    @classmethod
    def validate_id(cls, name, identifier):
        return len(identifier) == 36 and '-' in identifier and name in cls.acceptable_fields

    def get_messenger_info(self) -> dict:
        url = 'https://yandex.ru/messenger/api/registry/api/'
        data = {"method": "get_users_data", "params": {"guids": [self.identifier]}}
        r = requests.post(url, headers=HEADERS, cookies=self.cookies, files={'request': (None, json.dumps(data))})
        info = extract(r.text)
        if info:
            info['URL'] = f'https://yandex.ru/chat#/user/{self.identifier}'
        return info


def crawl(user_data: dict, cookies={}, checked_values=[]):
    entities = (YaUsername, YaPublicUserId, YaMessengerGuid)

    for k, v in user_data.items():
        values = list(v) if isinstance(v, set) else [v]
        for value in values:
            if value in checked_values:
                continue

            for e in entities:
                if not e.validate_id(k, value):
                    continue

                checked_values.append(value)

                print(f'[*] Get info by {k} `{value}`...\n')
                entity_obj = e(value, cookies)
                entity_obj.collect()
                entity_obj.print()

                crawl(entity_obj.info, cookies, checked_values)


def main():
    if len(sys.argv) > 1:
        username = sys.argv[1]
    else:
        username = input('Enter Yandex username / login / email: ')

    cookies = load_cookies(COOKIES_FILENAME)
    if not cookies:
        print(f'Cookies not found, but are required for some sites. See README to learn how to use cookies.')

    user_data = {'username': username.split('@')[0]}

    crawl(user_data, cookies)


if __name__ == '__main__':
    main()
