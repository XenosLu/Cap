#!/usr/bin/python3
# -*- coding:utf-8 -*-
"""xapi presenter"""
import os
import sys
import logging
import datetime
import time
import math
import json
import re
import asyncio

import yaml
import docker
import tornado.httpclient

from models import Task

UTC_FORMAT = '%Y-%m-%dT%H:%M:%S.%fZ'
TIME_FORMAT = '%Y-%m-%d %H:%M:%S'

        
def get_docker_client():
    """get docker client"""
    if sys.platform == 'win32':
        base_url = 'http://127.0.0.1:2375'
    else:
        base_url = 'unix://var/run/docker.sock'
    return docker.DockerClient(base_url=base_url, version='auto', timeout=50)


def get_datetime(utc_time_str):
    """get datetime from utc time string"""
    utc_time_str = '%sZ' % utc_time_str[:-4]
    utc_time = datetime.datetime.strptime(utc_time_str, UTC_FORMAT)
    local_time = utc_time - datetime.timedelta(seconds=time.timezone)
    return local_time


def time_level(from_datetime):
    """return time interval in human read format"""
    second = (datetime.datetime.now() - from_datetime).total_seconds()
    if second < 0:
        return 'from future:-)'
    if second == 0:
        return 'right now'
    if second < 86400:
        unit = ('seconds', 'minutes', 'hours')
        power = min(int(math.floor(math.log(second, 60))), 5)
        return '%d %s ago' % (second/60**power, unit[power])
    if second < 86400 * 30:
        return '%d days ago' % (second / 86400)
    if second < 86400 * 365:
        return '%d months ago' % (second / 86400 / 30)
    return '%d years ago' % (second / 86400 / 365)


def stamp_to_time(timestamp):
    """change utc to localtime, not used"""
    time_local = time.localtime(timestamp)
    return time.strftime(TIME_FORMAT, time_local)


def digit_now():
    """return current time in digit"""
    return time.strftime('%Y%m%d%H%M%S', time.localtime())
    # return datetime.datetime.now().strftime('%Y%m%d%H%M%S')


def get_size(size):
    """get file size in human read format from count"""
    if size < 0:
        return 'Out of Range'
    if size < 1024:
        return '%dB' % size
    unit = ' KMGTPEZYB'
    power = min(int(math.floor(math.log(size, 1024))), 9)
    return '%.1f%sB' % (size/1024.0**power, unit[power])


def self_deploy(tag):
    """deploy a temp container to update self"""
    stop_and_rename_container('cap_self_deploy')
    logging.info('starting updater: cap_self_deploy')
    para = {
        'detach': True,
        'name': 'cap_self_deploy',
        'volumes': {
            '/var/run/docker.sock':
                {'bind': '/var/run/docker.sock', 'mode': 'rw'}
            },
        'command': '/usr/bin/python3 /cap/self_deploy.py %s' % tag,
        'remove': True
        }
    get_docker_client().containers.run(image=tag, **para)


def deploy_container(tag):
    """deploy container"""
    if 'xenocider/cap' in tag:
        return self_deploy(tag)
    return stop_and_run_container(tag)


def stop_and_run_container(tag):
    """stop an old container and start a new one"""
    task = Task.select().where(Task.name == tag).get()
    logging.info('get run task: %s', task)
    container = stop_and_rename_container(task.containername)
    extra_para = {}
    if container and task.inheritvolume:
        extra_para = {'volumes_from': [container.id]}
    logging.info('deploy container %s with paras: %s %s', task.containername, task.parameters, extra_para)
    get_docker_client().containers.run(
        image=tag, name=task.containername, **task.parameters, **extra_para)


def stop_and_rename_container(name):
    """stop and rename an old container(to start a new one)"""
    # logging.info('try stopping container: %s', name)
    try:
        container = get_docker_client().containers.get(name)
        logging.info('Stopped old container: %s', name)
    except docker.errors.NotFound:
        logging.debug('no exist container %s', name)
        return None
    container.rename('%s_old_%s' % (name, digit_now()))
    container.stop()
    container.update(restart_policy = {'Name': 'no'})
    return container


def import_task():
    """if task not exist then import it from init yaml config file"""
    if not Task.select().first():
        logging.info('cannot find config from db, importing config')
        import_config()


def import_config(config_file='task.yml'):
    """import task config from yaml config file"""
    with open(config_file) as file_read:
        tasks = yaml.safe_load(file_read.read())
        for task in tasks:
            Task.replace(**task).execute()


def save_config():
    """save task table to yaml file, no longer used"""
    tasks = [task.__dict__['__data__'] for task in Task.select()]
    with open('config/task.yml', 'w') as file_write:
        file_write.write(yaml.dump(tasks))


def get_image_status(image):
    """check if image is used"""
    containers = get_docker_client().containers.list(all=True)
    for container in containers:
        if container.image.id == image.id:
            return 'deployed'
    if (datetime.datetime.now() - get_datetime(image.attrs['Created'])).days < 1:
        return 'new'
    return 'undeployed'


def update_job_generator():
    """update job generator"""
    logging.info('=== start update cron thread ===')
    import_task()
    while True:
        logging.info('sleep %ss', SLEEP_TIME)
        time.sleep(SLEEP_TIME)
        for task in list(Task.select().where(Task.isactive == True)):
            if check_update(task.name):
                task.last_updated = datetime.datetime.now()
                task.save()  # record the updated image
                if task.autodeploy:
                    try:
                        deploy_container(task.name)
                        yield '%s deployed' % task.name
                    except Exception as exc:
                        logging.info(exc, exc_info=True)
                        yield '%s deploy exception: %s\ndocker version: %s' % (
                            task.name, exc, VERSION)
                else:
                    yield 'image %s downloaded' % task.name

@asyncio.coroutine
def update_job_coroutine():
    """update job generator"""
    logging.info('=== start update cron thread ===')
    import_task()
    while True:
        for task in list(Task.select().where(Task.isactive == True)):
            yield
            if check_update(task.name):
                yield
                task.last_updated = datetime.datetime.now()
                task.save()  # record the updated image
                if task.autodeploy:
                    try:
                        deploy_container(task.name)
                        return '%s deployed' % task.name
                    except Exception as exc:
                        logging.info(exc, exc_info=True)
                        return '%s deploy exception: %s\ndocker version: %s' % (
                            task.name, exc, VERSION)
                else:
                    return 'image %s downloaded' % task.name


def check_update(task_name):
    """check image update"""
    logging.debug('checking %s', task_name)
    time0 = time.time()
    # run docker pull
    try:
        client = get_docker_client()
        current_list = client.images.list(all=True)
        update_image = client.images.pull(task_name)
    except docker.errors.ImageNotFound as exc:
        logging.info(exc)
        return None
    except Exception as exc:
        logging.warning(exc, exc_info=False)
        logging.info('docker pull error! sleep 120s')
        time.sleep(99)
        return None
    if not update_image in current_list:
        logging.info('image %s updated. cost %.02f seconds', task_name, time.time() - time0)
        logging.info(
            'created: %s', get_datetime(update_image.attrs['Created']).strftime(TIME_FORMAT))
        return update_image
    return None


def get_images():
    """get images info dict"""
    imgs = []
    for task in list(Task.select().where(Task.isactive == True).order_by(Task.last_updated.desc())):
        try:
            image = get_docker_client().images.get(task.name)
            imgs.append({
                'status': get_image_status(image),
                'id': image.id[7:19],
                'tag': task.name,
                'containername': task.containername,
                'autodeploy': task.autodeploy,
                'created': get_datetime(image.attrs['Created']).strftime(TIME_FORMAT),
                'size': get_size(image.attrs['Size']),
                'last_updated': time_level(task.last_updated),
                'last_build_state': task.last_build_state,
                })
            get_docker_client().close()
        except Exception as exc:
            logging.debug(exc)
    return imgs


def get_containers():
    """get containers info dict"""
    containers = [
        {'name': container.name,
         'status': container.status,
         'created': time_level(get_datetime(container.attrs['Created'])),
         'id': container.id[:12],
         'image': container.attrs['Config']['Image']
         }
        for container in get_docker_client().containers.list(all=True)]
    return containers


class JavascriptRPC():
    """RPC commands for javascript"""
    @classmethod
    def run(cls, method, args=None):
        """run RPC command"""
        args = [args[i] for i in sorted(args.keys())]
        logging.info('running method: %s with args: %s', method, args)
        try:
            return getattr(cls, method)(*args)
        except Exception as exc:
            logging.info(exc, exc_info=True)
            return {'result': 'danger', 'content': str(exc)}

    @classmethod
    def test(cls, *args):
        """test"""
        logging.info('start test %s', args)
        for i in range(5):
            time.sleep(1)
            logging.info('test sleep %d', i)
        return {'result': 'success', 'content': 'test'}

    @classmethod
    def reloadconfig(cls, *args):
        """reload config"""
        import_config()
        return {'result': 'success', 'content': 'reloaded.'}

    @classmethod
    def importconfig(cls, *args):
        """import config"""
        import_config('new.yml')
        return {'result': 'success', 'content': 'imported.'}

    @classmethod
    def pull(cls, *args):
        """git pull and self restart"""
        if sys.platform == 'linux':
            if os.system('git pull') == 0:
                python = sys.executable  # need to add a thread maybe
                os.execl(python, python, *sys.argv)
                return {'result': 'success', 'content': 'git pull done, waiting for restart'}
            return {'result': 'danger', 'content': 'execute git pull failed'}
        return {'result': 'danger', 'content': 'not supported'}


    @classmethod
    def makeautodeploy(cls, name, autodeploy, *args):
        """set autodeployf for task"""
        Task.update(autodeploy=autodeploy).where((Task.name == name)).execute()
        return {'result': 'success', 'content': 'Saved.'}

    @classmethod
    def deploy(cls, name, *args):
        """deploy container from image"""
        deploy_container(name)
        return {'result': 'success', 'content': 'deploy %s' % name}

    @classmethod
    def container(cls, action, cid, *args):
        """container operatoins: start/stop/remove"""
        logging.info('%s container %s', action, cid)
        container = get_docker_client().containers.get(cid)
        getattr(container, action)()
        return {'result': 'success', 'content': '%s container %s' % (action, container.name)}

    @classmethod
    def prune(cls, obj, *args):
        """prune methods"""
        try:
            result = getattr(get_docker_client(), obj).prune()
            logging.info(result)
            recliamed_space = get_size(result['SpaceReclaimed'])
            return {'result': 'success', 'content': 'Space Reclaimed: %s' % recliamed_space}
        except docker.errors.InvalidVersion as exc:
            logging.info(exc)
            return {'result': 'danger', 'content': str(exc)}

    @classmethod
    def pruneall(cls, *args):
        """prune methods"""
        recliamed_spaces = []
        for obj in ('images', 'containers', 'volumes'):
            result = getattr(get_docker_client(), obj).prune()
            logging.info(result)
            recliamed_spaces.append(result['SpaceReclaimed'])
        recliamed_space = get_size(sum(recliamed_spaces))
        return {'result': 'success', 'content': 'Space Reclaimed: %s' % recliamed_space}

    @classmethod
    def remove(cls, obj, *args):
        """remove image method"""
        Task.update(isactive=False).where(Task.name == obj).execute()
        get_docker_client().images.remove(obj)
        Task.delete().where(Task.name == obj).execute()
        return {'result': 'success', 'content': 'remove %s' % obj}


def get_state():
    """get all the states for page show"""
    return {'containers': get_containers(),
            'images': get_images(),
            'unused_volumes': len(get_unused_volumes())
            }


def get_unused_volumes():
    """get unused volumes"""
    volumes = {vol.attrs['Name'] for vol in get_docker_client().volumes.list()}
    used_volumes = set()
    for container in get_docker_client().containers.list(all=True):
        container_vol = {
            mount['Name'] for mount in container.attrs['Mounts'] if mount.get('Type') == 'volume'}
        used_volumes.update(container_vol)
    unused_volumes = volumes.symmetric_difference(used_volumes)
    if unused_volumes:
        logging.debug(unused_volumes)
    return unused_volumes


async def get_buildhistory_coroutine(author='xenocider', name='cap', tag='master'):
    """get build history from docker hub"""
    url = 'https://hub.docker.com/v2/repositories/%s/%s/buildhistory/?page_size=3' % (author, name)
    status_map = {0: 'Queued', 2:'Building', 3: 'Building', 10: 'Success', -1: 'Error'}
    http = tornado.httpclient.AsyncHTTPClient()
    try:
        response = await http.fetch(url)
        result = json.loads(response.body.decode())
    except Exception as exc:
        logging.warn('%s \nurl: %s' % (exc, url), exc_info=True)
        return None
    results = result.get('results')
    logging.debug('%s/%s:%s', author, name, tag)
    logging.debug(results)
    results = [i for i in results if i['dockertag_name'] == tag]
    if results:
        logging.debug(results[0])
        return status_map[results[0].get('status')]
    return None

 
async def check_build_status_coroutine(callback=logging.info):
    """check build status of image of tasks"""
    while True:
        for task in list(Task.select()):
            author, name, tag = re.split('/|:', task.name)
            state =  await get_buildhistory_coroutine(author, name, tag)
            if state and task.last_build_state != state:
                task.last_build_state = state
                task.save()
                callback('the build state of %s is %s' % (task.name, state))
            else:
                callback(None)
            await asyncio.sleep(3)

try:
    VERSION = get_docker_client().version()['Version']
except Exception:
    VERSION = 'not connected'

SLEEP_TIME = 9

if __name__ == '__main__':
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s %(filename)s %(levelname)s [line:%(lineno)d] %(message)s',
        datefmt=TIME_FORMAT)
    # print(get_images())
    import_task()

