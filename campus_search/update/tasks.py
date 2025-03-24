# celery的任务必须写在tasks.py的文件中，别的文件名称不识别!!!
# from CL.main import app
import time
from celery import shared_task
from search.views import searcher, proc_path


import logging
log = logging.getLogger("django")

import json

# r = redis.Redis(host='localhost', port=6379, db=0)  # 配置Redis

@shared_task  # name表示设置任务的名称，如果不填写，则默认使用函数名做为任务名
def send_sms():
    searcher.update(proc_path)
    # print("向手机号%s发送短信成功1!"%mobile)
    # time.sleep(5)

    # 将 index 序列化存入 Redis
    # r.set('searcher_index', json.dumps(searcher.index.__dict__))  # 假设index可以序列化
    print("searcher.index长度:", searcher.index.getlen())

    return searcher.to_dict()

# @app.task  # name表示设置任务的名称，如果不填写，则默认使用函数名做为任务名
# def send_sms2(mobile):
#     print("向手机号%s发送短信成功2!" % mobile)
#     time.sleep(5)

#     return "send_sms2 OK"