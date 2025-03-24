from django.shortcuts import render, HttpResponse
from django.apps import apps
import json


from search.util.searcher import Searcher
# from search.util.searcher import update
from django.core.paginator import Paginator

proc_path = "/root/proj/campus_search/spy_campus/spy_campus/student_affair.json"

# 获取单例实例
searcher = Searcher()
searcher.init_searcher()
# if not Task.objects.filter(task_name='search.util.searcher.update_search_index').exists():
# p_s = pickle.dumps(self.searcher)
# update.apply_async((p_s, proc_path), countdown=2)  # 每 2 秒执行一次

# from CL.update.tasks import send_sms,send_sms2
# send_sms.delay("110")

from celery import current_app
from campus_search.update.tasks import send_sms
from datetime import timedelta

import threading
import traceback

def schedule_task():
    try:
        searcher.update()
        # print("更新成功")
    except Exception as e:
        print("更新失败，异常信息如下：")
        traceback.print_exc()  # 打印详细异常信息
    finally:
        # 不论成功或失败，都继续 300 秒后再运行
        threading.Timer(300, schedule_task).start()

schedule_task()

def index(request):
    if request.method == 'POST':
        query = request.POST.get('query')
        # 调用你的搜索函数
        result = searcher.search(query)
        result = json.loads(result)
        
        # 分页，每页 20 条
        paginator = Paginator(result, 20)
        page_number = request.GET.get('page')
        page_obj = paginator.get_page(page_number)

        return render(request, 'index.html', {
            'items': page_obj,
            'query': query
        })

    else:  # GET 请求
        query = request.GET.get('query', '')
        result = []
        
        # 如果 query 存在，说明是翻页过来的
        if query:
            result = searcher.search(query)
            result = json.loads(result)

        paginator = Paginator(result, 20)
        page_number = request.GET.get('page')
        page_obj = paginator.get_page(page_number)

        return render(request, 'index.html', {
            'items': page_obj,
            'query': query
        })

