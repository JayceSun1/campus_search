import json
from typing import List, Dict, Optional
import jieba  # 导入 jieba 分词库
from search.util.index import Index, DocInfo, InvertedElem  # 假设 Index 类和相关结构已定义
# from background_task import background

import os
import dashscope
from http import HTTPStatus
import json

import dashscope
from dashscope import TextEmbedding

from dashvector import Client, Doc
import dashvector
import campus_search.settings as settings

# @shared_task
# def update(p_s, input_file: str):    
#     print("更新")
#     searcher = pickle.loads(p_s)
#     searcher.index.update_index(input_file=input_file)

# 模拟日志工具
class Log:
    @staticmethod
    def normal(message: str):
        print(f"[NORMAL] {message}")

# 模拟分词工具
class JiebaUtil:
    @staticmethod
    def cut_string(text: str) -> List[str]:
        # 使用 jieba 进行分词
        words = jieba.lcut(text)
        return [word.lower() for word in words]  # 转换为小写

# 倒排索引打印结构
class InvertedElemPrint:
    def __init__(self, doc_id: int = 0, weight: int = 0, words: Optional[List[str]] = None):
        self.doc_id = doc_id
        self.weight = weight
        self.words = words if words is not None else []

# 搜索器类
class Searcher:
    def __init__(self):
        self.index = None  # 索引对象
        self.input_file = None
        # embedding部分
        
        dashscope.api_key=settings.dashvector_api_key
        # 初始化 DashVector client
        self.client = Client(
        api_key=settings.cluster_api_key,
        endpoint=settings.cluster_endpoint
        )
        self.collection = self.client.get('sample')

    def generate_embeddings(self, text):
        rsp = TextEmbedding.call(model=TextEmbedding.Models.text_embedding_v1,
                                    input=text)

        embeddings = [record['embedding'] for record in rsp.output['embeddings']]
        return embeddings if isinstance(text, list) else embeddings[0]

    def init_searcher(self):
        # 获取或创建索引对象
        self.index = Index()
        Log.normal("获取单例成功...")

        # 根据索引对象建立索引结构
        self.index.build_index()
        print("BuildIndex over--------------")
        Log.normal("建立正排和倒排索引成功")

    def update(self):
        self.index.update_index()

    def search(self, query: str) -> str:
        # 1. 分词：对 query 进行分词
        words = JiebaUtil.cut_string(query)

        # 2. 触发：根据分词的各个“词”，进行索引查找
        tokens_map: Dict[int, InvertedElemPrint] = {}
        inverted_list_all: List[InvertedElemPrint] = []

        for word in words:
            word = word.lower()  # 忽略大小写
            # 先查倒排，获得倒排拉链
            inverted_list = self.index.get_inverted_list(word)
            
            if inverted_list is None:
                continue

            # 把所有的拉链保存在一起
            for elem in inverted_list:
                item = tokens_map.get(elem.doc_id, InvertedElemPrint())
                item.doc_id = elem.doc_id
                item.weight += elem.weight
                item.words.append(elem.word)
                tokens_map[elem.doc_id] = item

        # 语义部分
        semantic_scores = {}
        rsp = self.collection.query(self.generate_embeddings(query), output_fields=['title','doc_id','content','url','departmentt'])
        for doc in rsp.output:
            print(f"doc_id: {doc.fields['doc_id']}, title: {doc.fields['title']}, score: {doc.score}")

        for doc in rsp.output:
            doc_id = doc.fields['doc_id']
            score = doc.score
            semantic_scores[doc_id] = 1 / score + 1e-6  # 记录语义得分
            item = tokens_map.get(doc_id, InvertedElemPrint())
            item.doc_id = doc_id
            item.words.append(doc.fields['title'])
            tokens_map[doc_id] = item

        # -----------------------归一化开始--------------------------

        # 1. 获取正排匹配得分
        traditional_scores = {doc_id: item.weight for doc_id, item in tokens_map.items()}

        # 2. Min-Max Normalization
        def normalize(score_dict):
            scores = list(score_dict.values())
            if len(scores) == 0:
                return {}
            min_score = min(scores)
            max_score = max(scores)
            norm_scores = {}
            for doc_id, score in score_dict.items():
                norm_score = (score - min_score) / (max_score - min_score + 1e-6)
                norm_scores[doc_id] = norm_score
            return norm_scores

        norm_traditional = normalize(traditional_scores)
        norm_semantic = normalize(semantic_scores)

        # -----------------------线性融合-----------------------------
        alpha = 0.5  # 可调节传统匹配和语义匹配的权重

        for doc_id, item in tokens_map.items():
            traditional = norm_traditional.get(doc_id, 0)
            semantic = norm_semantic.get(doc_id, 0)
            final_score = alpha * traditional + (1 - alpha) * semantic
            item.weight = final_score  # 最终得分


        # 将 tokens_map 转换为列表
        inverted_list_all = list(tokens_map.values())

        # 3. 合并排序：根据汇总查找结果，按照相关性（weight）降序排序
        inverted_list_all.sort(key=lambda x: x.weight, reverse=True)

        # 4. 构建：根据查找结果，构建 JSON 串
        root = []
        for item in inverted_list_all:
            doc = self.index.get_forward_index(item.doc_id)
            if doc is None:
                continue

            elem = {
                "doc_id": doc.doc_id,
                "title": doc.title,
                "desc": self.get_desc(doc.content, item.words[0]),  # 获取描述
                "url": doc.url,
                "score": item.weight
            }
            root.append(elem)

        # 将 JSON 对象转换为字符串
        json_string = json.dumps(root, ensure_ascii=False, indent=2)
        return json_string

    def get_desc(self, html_content: str, word: str) -> str:
        # 找到 word 在 html_content 中首次出现的位置
        # 然后往前找 50 字节，往后找 100 字节，截取这部分内容
        prev_step = 50
        next_step = 100

        # 1. 找到首次出现
        pos = html_content.lower().find(word.lower())
        if pos == -1:
            return "None1"

        # 2. 获取 start 和 end
        start = max(0, pos - prev_step)
        end = min(len(html_content), pos + next_step)

        # 3. 截取字串
        if start >= end:
            return "None2"
        desc = html_content[start:end]
        desc += "..."
        return desc

# 测试代码
if __name__ == "__main__":
    # 初始化搜索器
    searcher = Searcher()
    searcher.init_searcher()

    # 执行搜索
    query = "我想写毕业论文，我是信智学院2021级的学生，请帮我找相关通知"
    result = json.loads(searcher.search(query))
    # print(result[0])
    for item in result:
        print(f"doc_id: {item['doc_id']}, title: {item['title']}, score: {item['score']}")
        # print(item)
    # print(result)
    print('----------------------------------')
    # 基于向量检索的语义搜索
    # rsp = searcher.collection.query(searcher.generate_embeddings(query), output_fields=['title'])

    # for doc in rsp.output:
        # print(f"id: {doc.id}, title: {doc.fields['title']}, score: {doc.score}")