import os
import json
import threading
from collections import defaultdict
from typing import List, Dict, Optional
import jieba  # 导入 jieba 分词库
from datetime import date
import time
import pymysql

# 模拟日志工具
class Log:
    @staticmethod
    def normal(message: str):
        print(f"[NORMAL] {message}")

# 模拟字符串工具
class StringUtil:
    @staticmethod
    def split(line: str, sep: str) -> List[str]:
        return line.split(sep)

# 使用 jieba 分词
class JiebaUtil:
    @staticmethod
    def cut_string(text: str) -> List[str]:
        # 使用 jieba 进行分词
        words = jieba.lcut(text)
        return [word.lower() for word in words]  # 转换为小写

# 文档信息结构
class DocInfo:
    def __init__(self, title: str, content: str, url: str, dept: str, time:date, doc_id: int):
        self.title = title      # 标题
        self.content = content  # 文章内容
        self.url = url          # 文章url
        self.time = time        # 文章发布时间
        self.dept = dept        # 发文部门
        self.doc_id = doc_id    # 文档id

# 倒排索引元素结构
class InvertedElem:
    def __init__(self, doc_id: int, word: str, weight: int):
        self.doc_id = doc_id # 文档id
        self.word = word     # 关键词
        self.weight = weight # 文档对应关键词的权重

# 倒排拉链类型
InvertedList = List[InvertedElem]

# 索引类
class Index:
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super(Index, cls).__new__(cls)
                    cls._instance.forward_index = []  # 正排索引
                    cls._instance.inverted_index = defaultdict(list)  # 倒排索引
                    cls._instance.last_count = 0
                    cls._instance.conn = pymysql.connect(host='127.0.0.1', port=3306, user='root', passwd='', charset='utf8', db='campus_search', cursorclass=pymysql.cursors.DictCursor)
                    cls._instance.cursor = cls._instance.conn.cursor(cursor=pymysql.cursors.DictCursor)
                    cls._instance.notices_table_name = 'notificationitems'
                    cls._instance.teachers_table_name = 'teacheritems'
        return cls._instance

    def getlen(self):
        return len(self.forward_index), len(self.inverted_index)

    # 根据 doc_id 获取文档内容
    def get_forward_index(self, doc_id: int) -> Optional[DocInfo]:
        if doc_id >= len(self.forward_index):
            print(f"doc_id {doc_id} out of range")
            return None
        return self.forward_index[doc_id]

    # 根据关键字获取倒排拉链
    def get_inverted_list(self, word: str) -> Optional[InvertedList]:
        if word not in self.inverted_index:
            print(f"{word} has no InvertedList")
            return None
        return self.inverted_index[word]

    def update_index(self):
        # if not os.path.exists():
        #     print(f"sorry, {input_file} open error")
        #     return False
        # with open(input_file, "r", encoding="utf-8") as f:
        # data = json.load(f)
        try:
            with self.conn.cursor() as cursor:
                # 执行 SQL 查询
                sql = f"SELECT * FROM {self.notices_table_name}"
                self.cursor.execute(sql)

                # 获取所有数据
                data = self.cursor.fetchall()
                Log.normal(type(data[0]))
        except pymysql.err.InterfaceError as e:
            print(f"数据库连接异常: {e}")
            self.reconnect()  # 重新连接
            self.cursor.execute(sql)  # 重新执行查询
        except Exception as e:
            print(f"执行 SQL 查询时发生错误: {e}")
        # finally:
        #     # 关闭数据库连接
        #     self.conn.close()

        if len(data) > self.last_count:
            Log.normal(f'update from {self.last_count} to {len(data)}')
            for line in data[self.last_count:]:
                doc = self._build_forward_index(line)
                if doc is None:
                    print(f"build {line} error")
                    continue
                self._build_inverted_index(doc)
            self.last_count = len(data)
        # print('-------------------------------------------------------')

    # 构建索引
    def build_index(self) -> bool:
        try:
            with self.conn.cursor() as cursor:
                # 执行 SQL 查询
                sql = f"SELECT * FROM {self.notices_table_name}"
                self.cursor.execute(sql)

                # 获取所有数据
                data = self.cursor.fetchall()
                print(type(data[0]))
        except pymysql.err.InterfaceError as e:
            print(f"数据库连接异常: {e}")
            self.reconnect()  # 重新连接
            self.cursor.execute(sql)  # 重新执行查询
        except Exception as e:
            print(f"执行 SQL 查询时发生错误: {e}")
            
        count = 0
        for line in data:
            # line = line.strip()
            doc = self._build_forward_index(line)
            if doc is None:
                print(f"build {line} error")
                continue
            self._build_inverted_index(doc)
            count += 1
            if count % 1000 == 0:
                Log.normal(f"当前已经建立的索引文档: {count}")
        self.last_count = len(data)
        return True

    # 构建正排索引
    def _build_forward_index(self, line: dict) -> Optional[DocInfo]:
        doc = DocInfo(
            title=line['title'],
            content=line['content'],
            url=line['url'],
            time=line['pub_time'],
            dept=line['dept'],
            doc_id=line['doc_id']
        )
        self.forward_index.append(doc)
        return doc

    # 构建倒排索引
    def _build_inverted_index(self, doc: DocInfo) -> bool:
        word_map = defaultdict(lambda: {"title_cnt": 0, "content_cnt": 0})

        # 拆分标题并统计词频
        title_words = JiebaUtil.cut_string(doc.title)
        for word in title_words:
            word_map[word]["title_cnt"] += 1

        # 拆分内容并统计词频
        content_words = JiebaUtil.cut_string(doc.content)
        for word in content_words:
            word_map[word]["content_cnt"] += 1

        # 构建倒排索引
        X = 100
        Y = 1
        for word, cnt in word_map.items():
            weight = X * cnt["title_cnt"] + Y * cnt["content_cnt"]
            inverted_elem = InvertedElem(doc_id=doc.doc_id, word=word, weight=weight)
            self.inverted_index[word].append(inverted_elem)

        return True

# 测试代码
if __name__ == "__main__":
    # 文件路径
    # proc_path = "./raw.txt"
    # proc_path = "./student_affair.json"

    # 获取单例实例
    index = Index()

    # 构建索引
    if index.build_index():
        print("索引构建成功")

    # 测试正排索引
    doc = index.get_forward_index(0)
    if doc:
        print(f"文档 0 的标题: {doc.title}")

    # 测试倒排索引
    inverted_list = index.get_inverted_list("校级")
    if inverted_list:
        for elem in inverted_list:
            print(f"关键词: {elem.word}, 文档 ID: {elem.doc_id}, 权重: {elem.weight}")


