#!/usr/bin/python3
# -*- coding:utf-8 -*-
"""cap"""
import os
import logging
import json
import asyncio
import time
from functools import wraps
from concurrent.futures import ThreadPoolExecutor

import tornado.web
import tornado.websocket

from presenter import VERSION, get_state, JavascriptRPC
from presenter import update_job_generator
from presenter import update_job_coroutine, SLEEP_TIME  # not used
from presenter import check_build_status_coroutine
from github_oauth_async import GithubOauthAsync

oauth = GithubOauthAsync()


def authenticated_async(login='XenosLu'):
    def decorator(func):
        @wraps(func)
        async def wrapper(self, *args, **kwargs):
            token = self.get_secure_cookie('github_access_token')
            if not token:
                self.redirect(oauth.authorize_redirect_url)
                return
            token = token.decode()
            res = await oauth.get_user_with_cache(token)
            if not res.get('login') == login:
                self.send_error(401)
                return
            self.current_user = res.get('login')
            await func(self, *args, **kwargs)
        return wrapper
    return decorator


class IndexHandler(tornado.web.RequestHandler):
    """index web page"""
    def data_received(self, chunk):
        pass

    @authenticated_async()
    async def get(self, *args, **kwargs):
        self.render('index.html', version=VERSION)


class LoginHandler(tornado.web.RequestHandler):
    """login page"""

    def data_received(self, chunk):
        pass

    async def get(self, *args, **kwargs):
        code = self.get_argument('code', default='')
        if not code:
            self.send_error(401)
            return
        data = await oauth.get_token(code)
        print(data)
        access_token = data.get('access_token')
        if access_token is None:
            self.send_error(401)
            return
        self.set_secure_cookie('github_access_token', access_token)
        self.redirect('/')


class LinkWebSocketHandler(tornado.websocket.WebSocketHandler):
    """Info retriever use web socket"""
    executor = ThreadPoolExecutor(6)
    users = set()
    last_message = {}

    def data_received(self, chunk):
        pass

    # @authenticated_async()
    async def open(self, *args, **kwargs):
        token = self.get_secure_cookie('github_access_token')
        logging.info(token)
        logging.info(self.__bases__)
        # if not token:
            # self.redirect(oauth.authorize_redirect_url)
            # return
        # token = token.decode()
        # res = await oauth.get_user_with_cache(token)
        # if not res.get('login') == login:
            # self.send_error(401)
            # return
        # self.current_user = res.get('login')
        
        logging.info('Websocket connected: %s', self.request.remote_ip)
        self.users.add(self)
        self.write_message(self.last_message)

    # @tornado.concurrent.run_on_executor
    def on_message(self, message):
        """message should be like {'method':'cmd', 'args':{'0':'args1'}}"""
        logging.info('received ws message: %s', message)
        message = json.loads(message)
        # result = JavascriptRPC.run(**message)
        # self.write_message(result)
        self.executor.submit(
            JavascriptRPC.run, **message).add_done_callback(self.callback_write_message)

    def on_close(self):
        logging.info('ws close: %s', self.request.remote_ip)
        self.users.remove(self)

    def write_message(self, message, binary=False):
        try:
            asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        super().write_message(message, binary)

    def callback_write_message(self, obj):
        """call back for write message using thread pool"""
        self.write_message(obj.result())

    @classmethod
    def write_message_all(cls, obj):
        """write message to all websocket clients"""
        for i in cls.users:
            i.write_message(obj)

    @classmethod
    def retrieve_state(cls):
        """retrieve dataa of states periodly"""
        while True:
            while not cls.users:
                time.sleep(1)
            try:
                state = get_state()
            except Exception as exc:
                logging.info(exc, exc_info=True)
                state = {'result': 'danger', 'content': str(exc)}
            if state != cls.last_message:
                cls.write_message_all(state)
                cls.last_message = state.copy()
            time.sleep(3)

    @classmethod
    def auto_update(cls):
        """auto_update_task"""
        try:
            for result in update_job_generator():
                logging.info(result)
                cls.write_message_all({'notification': result})
        except Exception as exc:
            logging.info(exc, exc_info=True)

    @classmethod
    def callback_notification(cls, status):
        """callback notification"""
        if status:
            logging.info(status)
            cls.write_message_all({'notification': status})

    @classmethod
    def run_task(cls):
        """run tasks through thread pool"""
        cls.executor.submit(cls.auto_update)
        # cls.executor.submit(cls.retrieve_state)
        # cls.executor.submit(run_tasks_coroutine)

async def retrieve_state_coroutine():
    """retrieve data of states periodly"""
    while True:
        try:
            state = get_state()
            logging.info('retrieve_state')
            logging.debug(state)
        except Exception as exc:
            logging.info(exc, exc_info=True)
            state = {'result': 'danger', 'content': str(exc)}
        if state != LinkWebSocketHandler.last_message:
            LinkWebSocketHandler.write_message_all(state)
            LinkWebSocketHandler.last_message = state.copy()
        while not LinkWebSocketHandler.users:
            logging.info('sleep')
            await asyncio.sleep(1)
        await asyncio.sleep(2.8)

async def auto_update_coroutine():
    """auto_update_task"""
    try:
        while True:
            result = await update_job_coroutine()
            logging.info(result)
            if result:
                LinkWebSocketHandler.write_message_all({'notification': result})
            logging.info('sleep')
            # await asyncio.sleep(SLEEP_TIME)
    except Exception as exc:
        logging.info(exc, exc_info=True)

def prune_images():
    """cron job prune images"""
    logging.info('auto prune images start running')
    LinkWebSocketHandler.executor.submit(JavascriptRPC.run, method='prune', args={'0': 'images'})

HANDLERS = [
    (r'/', IndexHandler),
    (r'/login', LoginHandler),
    (r'/link', LinkWebSocketHandler),
    (r'/(.*\.db)', tornado.web.StaticFileHandler, {'path':'config'}),  # for test
]

SETTINGS = {
    'static_path': 'static',
    'template_path': '',
    'gzip': True,
    "cookie_secret": 'cap_secret',
    'debug': True,
}

# initialize logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(filename)s %(levelname)s [line:%(lineno)d] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S')
APP = tornado.web.Application(HANDLERS, **SETTINGS)

# prune images every 30 minutes
tornado.ioloop.PeriodicCallback(prune_images, 1800000).start()

loop = asyncio.get_event_loop()
loop.create_task(check_build_status_coroutine(LinkWebSocketHandler.callback_notification))
# loop.create_task(auto_update_coroutine())
loop.create_task(retrieve_state_coroutine())

LinkWebSocketHandler.run_task()


if __name__ == "__main__":
    os.chdir(os.path.dirname(os.path.abspath(__file__)))  # set file path as current
    APP.listen(8888)
    tornado.ioloop.IOLoop.instance().start()
