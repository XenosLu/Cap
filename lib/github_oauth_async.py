#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""oauth_test.py"""
import os
import urllib
import asyncio

import requests_async as requests


class GithubOauthAsync:
    _OAUTH_AUTHORIZE_URL = 'https://github.com/login/oauth/authorize'
    _OAUTH_ACCESS_TOKEN_URL = 'https://github.com/login/oauth/access_token'
    _OAUTH_USERINFO_URL = 'https://api.github.com/user'
    user_list = {}

    def __init__(self, client_id=None, client_secret=None, redirect_uri=''):
        if not client_id:
            client_id = os.environ.get('GITHUB_CLIENT_ID', 'fd50922eacf5843c9ac3')
        if not client_secret:
            client_secret = os.environ.get('GITHUB_CLIENT_SECRET', '34a99a908f61d106688897a2882547c6d712b6f2')
        self.client_id = client_id
        self.client_secret = client_secret
        self.redirect_uri = redirect_uri
        self.authorize_redirect_url = self.get_authorize_url()

    async def get_token(self, code):
        url = self._OAUTH_ACCESS_TOKEN_URL
        querystring = {
            'client_id': self.client_id,
            'client_secret': self.client_secret,
            'code': code,
            'redirect_uri': self.redirect_uri}
        headers = {'Accept': 'application/json'}
        response = await requests.post(url, headers=headers, params=querystring)
        return response.json()

    def get_authorize_url(self):
        params = {
            'client_id': self.client_id,
            'scope': ['read:user'],
            'response_type': 'code',
        }
        return '%s?%s' % (self._OAUTH_AUTHORIZE_URL, urllib.parse.urlencode(params))

    async def get_user(self, access_token):
        url = self._OAUTH_USERINFO_URL
        headers = {
            'Authorization': 'token %s' % access_token
        }
        response = await requests.get(url, headers=headers)
        return response.json()

    async def get_user_with_cache(self, access_token=None):
        if isinstance(access_token, bytes):
            access_token = access_token.decode()
        if not isinstance(access_token, str):
            return {}
        response = self.user_list.get(access_token)
        if response:
            return response
        else:
            self.user_list[access_token] = await self.get_user(access_token)
            return self.user_list[access_token]


if __name__ == '__main__':
    oauth = GithubOauthAsync()
    print(oauth.get_authorize_url())
