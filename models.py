#!/usr/bin/python3
# -*- coding:utf-8 -*-
"""models for docker downloader"""
import os
import json
import datetime

from peewee import Model, SqliteDatabase, CharField, DateTimeField, BooleanField
# from peewee import FloatField

os.chdir(os.path.dirname(os.path.abspath(__file__)))  # set file path as current

database = SqliteDatabase('config/test09.db')

class JsonField(CharField):
    """model field to store data in json"""
    def __init__(self, *args, **kwargs):
        super(JsonField, self).__init__(*args, **kwargs)

    def db_value(self, value):
        return json.dumps(value)

    def python_value(self, value):
        return json.loads(value)


class BaseModel(Model):
    """Base model of peewee"""
    class Meta:
        database = database


class Image(BaseModel):
    """docker image table, no longer used"""
    id = CharField(primary_key=True)
    name = CharField(null=True)
    created = CharField(null=True)
    task = CharField(null=True)
    flag = CharField(null=True)
    time = DateTimeField(default=datetime.datetime.now)


class Task(BaseModel):
    """docker task table"""
    name = CharField(primary_key=True)
    containername = CharField(null=True)
    isactive = BooleanField(default=True)
    autodeploy = BooleanField(default=False)
    notification = BooleanField(default=False)
    parameters = JsonField(default='null')
    inheritvolume = BooleanField(default=False)
    last_updated = DateTimeField(default=datetime.datetime.now)
    last_build_state = CharField(null=True)


database.create_tables([Image, Task])


if __name__ == '__main__':
    database.drop_tables([Task])
    database.create_tables([Task])
