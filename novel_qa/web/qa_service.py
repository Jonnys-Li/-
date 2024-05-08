import json
import os
import jieba
from py2neo import Graph
import requests
from novel_qa.settings import BASE_DIR

graph = Graph('http://localhost:7474', auth=('neo4j', 'root'))

# 初始化实体识别字典
dict_path = os.path.join(BASE_DIR,'web/data/dict.txt')
word_dict = [ i.strip('\n') for i in open(dict_path,'r',encoding='utf-8').readlines()]
# 实体名称映射到实体类型
entity2type = {}
for word in word_dict:
    tmp_list = word.split('\t')
    if len(tmp_list)==2:
        # 将词典添加到jieba分词的自定义词典中
        jieba.add_word(tmp_list[0])
        entity2type[tmp_list[0]] = tmp_list[1]

# 通过自定义词典获取实体
def get_enyity(input_str):
    word_cut_dict = []
    # 对用户问句进行分词
    for word in jieba.cut(input_str.strip()):
        if word in entity2type:
            word_cut_dict.append(word)
    return  list(set(word_cut_dict))

# 提示词模板
PROMPT_TEMPLATE = """已知信息：
{context} 
根据上面提供的三元组信息，简洁和专业的来回答用户的问题。如果无法从中得到答案，请你根据你的理解回答用户问题。问题是：{question}"""


PROMPT_TEMPLATE1 = """请你用你的已有知识，简洁和专业的来回答用户的问题。如果无法从中得到答案，请你根据你的理解回答用户问题。问题是：{question}"""

# 获取提示词模板
def get_prompt(question, context):
    # 如果问题和neo4j查询到的上下文都不为空，则拼接出一个提示词，提交给大模型
    if len(question) and len(context)>0:
        prompt = PROMPT_TEMPLATE.format(context=context, question=question)
    # 如果neo4j查询到的数据为空，则提交问题给大模型
    else:
        prompt = question
    return prompt


# 从neo4j查询三元组
def search_entity_from_neo4j(question,entitys):
    triplet_list = []
    # 拼接cypher语句
    vis_query = []
    for e in entitys:
        query_str = 'a.Name contains(\'' + e + '\')'
        vis_query.append(query_str)

    # 拼接查询条件
    condition = ' or '.join(vis_query)
    query_str = 'MATCH (a) WITH a MATCH p = (a)-[*1..1]-() WHERE '+condition+' RETURN extract(r in relationships(p) | [startNode(r).Name, type(r), endNode(r).Name]) AS triplets'
    print(query_str)
    result = graph.run(query_str).data()
    if len(result) > 0:
        for i in result:
            triplet_list.extend(i['triplets'])
        triplet_list = ['(' + ','.join([str(x) for x in i]) + ')' for i in triplet_list]
        # 三元组去重
        triplet_list = list(set(triplet_list))
        return get_prompt(question=question, context='\n'.join(triplet_list)[:4096])
    else:
        # 未查询到三元组，直接返回空字符串
        return get_prompt(question=question, context='')

def get_answer(input_str):
    input_str = input_str.replace(' ', '').strip()
    # 预测实体
    entitys = get_enyity(input_str)
    print(entitys)
    # 如果识别到实体
    if len(entitys)>0:
        # 先查询实体相关的三元组，并拼接出提示词
        prompt = search_entity_from_neo4j(input_str, entitys)
        print(prompt)
        # 从大模型获取答案
        answer = get_answer_from_glm3(prompt)
        # 返回答案和查询语句
        return answer
    # 未查询到实体，直接从大模型获取答案
    else:
        print('未识别到实体，直接提交问题给大模型')
        prompt = PROMPT_TEMPLATE1.format( question=input_str)
        answer = get_answer_from_glm3(prompt)
        # 返回答案和查询语句
        return answer

def get_answer_from_glm3(prompt):
    url = 'http://127.0.0.1:7861/chat/chat'
    headers = {
        'Content-Type': 'application/json'
    }
    data = {
        "query": prompt,
        "history": [
        ],
        "conversation_id": "xxxxxx",
        "history_len": 5,
        "stream": False,
        "model_name": "chatglm3-6b",
        "temperature": 0.7,
        "max_tokens": 0,
        "prompt_name": "default"
    }
    print(data)
    response = requests.post(url, headers=headers, data=json.dumps(data))
    body = response.content.decode('utf-8')
    json_data = json.loads(body.replace('data: ', ''))
    print(json_data)
    text = json_data["text"]
    return text

