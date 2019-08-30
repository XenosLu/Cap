#!/usr/bin/python3
# -*- coding:utf-8 -*-
"""cron"""
import os
import logging

from presenter import update_job

os.chdir(os.path.dirname(os.path.abspath(__file__)))  # set file path as current

# initialize logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(filename)s %(levelname)s [line:%(lineno)d] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S')


if __name__ == '__main__':
    update_job()
