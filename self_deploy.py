#!/usr/bin/python3
# -*- coding:utf-8 -*-
"""deploy self"""
import sys
import logging
from presenter import stop_and_run_container, import_task

# initialize logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(filename)s %(levelname)s [line:%(lineno)d] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S')

import_task()
if len(sys.argv) == 2:
    container_name = sys.argv[1]
else:
    container_name = 'xenocider/cap:master'
logging.info('start deploying %s', container_name)
stop_and_run_container(container_name)
