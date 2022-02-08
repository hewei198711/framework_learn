# -*- coding: utf-8 -*-
"""
    generate_case_csv_file.py
    ~~~~~~~~~~~~~~~~~~~~~~~

    将测试用例xmind转换为csv导入的格式


    :author: ligeit
    :copyright: (c) 2020, May
    :date created: 2020-05-04
    :python version: 3.8

    安装依赖：
        pip install requests
        pip install xmindparser

    Usage:
        1. 将xmind文件导出为csv文件：
            python generate_case_csv_file.py xmind文件

        2. 导出的csv文件需自行手动导入jira&禅道，导入时注意检查。



"""
import sys
import os
import csv
import json
import hashlib

import requests
from xmindparser import xmind_to_dict


class ZentaoSession(requests.Session):
    url_root = 'http://zentao-lg.perfect99.com:10034'
    url_login = url_root + '?m=user&f=login&t=json'
    url_get_modules = url_root + '?m=testcase&t=json'
    url_create_modules = url_root + '?m=tree&f=manageChild&root={_id}&view=case&t=json'
    url_pre_page = url_root + '?m=tree&f=browse&productID={_id}&view=case'

        
    def login(self, account, password):
        cred = {
            'account': account,
            'password': hashlib.md5(password.encode('utf8')).hexdigest(),
            'keepLogin[]': 'on'
        }
        r = self.post(self.url_login, data=cred)
        # return r.status_code == 200 and r.json()['status'] == 'success'
        return r.status_code == 200

    def set_product_in_cookies(self, product_name):
        r = self.get(self.url_get_modules)
        # if r.status_code == 200 and r.json()['status'] == 'success':
        if r.status_code == 200:
            products = json.loads(r.json()['data'])['products']
            self.product_path_id_map = {v: k for k, v in products.items()}
        if product_name in self.product_path_id_map:
            self.product_id = self.product_path_id_map[product_name]
        else:
            print('项目不存在：' + product_name)
            exit(0)
        temp_cookie = requests.cookies.RequestsCookieJar()
        temp_cookie.set(
            'lastProduct', str(self.product_id),
            domain='172.16.1.55:7001', path='/zentao/')
        temp_cookie.set(
            'preProductID', str(self.product_id),
            domain='172.16.1.55:7001', path='/zentao/')
        self.cookies.update(temp_cookie)
        return self

    def get_modules_of_product(self, product_name):
        self.set_product_in_cookies(product_name)
        r = self.get(self.url_get_modules)
        if r.status_code == 200 and r.json()['status'] == 'success':
            self.zentao_data = json.loads(r.json()['data'])
            modules = self.zentao_data['modules']
            if modules == ['/']:
                modules = {'0': '/'}
            self.module_path_id_map = {v: k for k, v in modules.items()}
            return self.module_path_id_map
        else:
            print('Failed to get modules of product')
            
    def get_new_modules(self, modules, product_name):
        self.get_modules_of_product(product_name)
        zentao_modules = list(self.module_path_id_map.keys())
        new_modules = [_ for _ in modules if _ not in zentao_modules]
        return new_modules

    def trans_modules_to_tree(self, modules):
        module_tree = {}

        for m in modules:
            m_path = m[1:].split('/')
            current_root = module_tree
            for p in m_path:
                if p not in current_root:
                    current_root[p] = {}
                current_root = current_root[p]
        return module_tree
            
    def create_module_tree(self, module_tree, product_name, pre_module_str=''):
        self.get_modules_of_product(product_name)
        next_layer_modules = list(module_tree.keys())
        must_create_modules = [
            _ for _ in next_layer_modules
            if pre_module_str+'/'+_ not in self.module_path_id_map
        ]
        if len(must_create_modules) > 0:
            if pre_module_str:
                parent_module_id = self.module_path_id_map[pre_module_str]
            else:
                parent_module_id = '0'
            self.create_modules_in_target(
                parent_module_id, must_create_modules
            )
        for k, v in module_tree.items():
            self.create_module_tree(
                v, product_name, pre_module_str=pre_module_str+'/'+k)
    
    def create_modules_in_target(self, parent_id, modules):
        for m in modules:
            url = self.url_create_modules.format(_id=self.product_id)
            print('url: ' + url)
            r = self.post(
                url, data={'modules[]': m, 'parentModuleID': parent_id}
            )
            r.encoding='utf-8'
            if 'alert' in r.text:
                print('在模块%s下创建模块%s时返回警告：%s' % (parent_id, m, str(r.text)))
            else:
                print('在模块%s下创建模块%s成功' % (parent_id, m))
    
    def create_case_modules(self, modules, product_name):
        new_modules = self.get_new_modules(modules, product_name)
        print('需要创建的禅道新用例模块：')
        print(new_modules)
        module_tree = self.trans_modules_to_tree(new_modules)
        self.create_module_tree(module_tree, product_name)
        
    def update_csv_case_module_id(self, csv_file, product_name):
        with open(csv_file, 'r', encoding='gbk') as f:
            reader = csv.reader(f)
            case_list = list(reader)
        self.get_modules_of_product(product_name)
        for case in case_list[1:]:
            if case[0] in self.module_path_id_map:
                case[0] = '%s(#%s)' % (case[0], self.module_path_id_map[case[0]])
            else:
                print('模块不存在或已包含id：' + case[0])
        with open(csv_file, 'w', newline='', encoding='gbk') as csvfile:
            writer = csv.writer(csvfile)
            writer.writerows(case_list)
            print('已更新csv文件中的所属模块，添加了模块id')

def parser_tree_to_list(root_value, tree, current_layer, pre_topics, case_list):
    if 'topics' not in tree:
        pre_topics.pop()
        found_max_layer = current_layer
        return tree['title'], found_max_layer
    else:
        found_max_layer = 0
        tail_topic_list = []
        for node in tree['topics']:
            pre_topics.append(node['title'])
            tail_topic, max_layer = parser_tree_to_list(
                root_value, node, current_layer+1,
                pre_topics, case_list
            )
            found_max_layer = max(found_max_layer, max_layer)
            tail_topic_list.append(tail_topic)
        layer_to_final = found_max_layer - current_layer
        if layer_to_final == 2:
            # 生成步骤和预期
            step_list, expect_list = [], []
            step_list.append('%d. %s' % (1,  '-'.join(pre_topics[:-5])))
            expect_list.append('%d. %s' % (1, "进入用例测试页面"))
            for i, step_and_expect in enumerate(tail_topic_list,start=2):
                if isinstance(step_and_expect, str):
                    step_list.append('%d. %s' % (i, step_and_expect))
                    expect_list.append('%d. ' % (i))
                else:
                    step_list.append('%d. %s' % (i, step_and_expect[0]))
                    expect_list.append('%d. %s' % (i, step_and_expect[1]))
            # 生成所属模块
            for mark in  ['成功路径', '失败路径']:
                if mark in pre_topics[:-3]:
                    split_index = pre_topics.index(mark)
                    case_module = '/' + '/'.join(pre_topics[:split_index])
                    break
            else:
                case_module = '/' + '/'.join(pre_topics[:-4])
            # 生成关键词
            if pre_topics[-2] is None:
                keyword = None
            else:
                keyword = pre_topics[-2]
            # 添加用例
            case_list.append([
                case_module, None, pre_topics[-3], keyword, pre_topics[-1],
                ':'.join(pre_topics[-5:-3]),
                '\n'.join(step_list), '\n'.join(expect_list),
                "功能测试", "功能测试阶段"
            ])
            pre_topics.pop()
            return '', found_max_layer
        elif layer_to_final < 2:
            if len(tail_topic_list) > 1:
                print('错误：步骤有多于1个的预期！！！')
                print(str(pre_topics) + ', ' + tree['title'])
                exit(0)
            else:
                pre_topics.pop()
                return [tree['title'], tail_topic_list[0]], found_max_layer
        else:
            pre_topics.pop()
            return '', found_max_layer


def tree_to_case_list(tree, root_value):
    # 将xmind树转换为每一行的用例结构

    _case_list = []
    for topic in tree['topic']['topics']:
        parser_tree_to_list(
            root_value, topic, current_layer=1,
            pre_topics=[topic['title']], case_list=_case_list
        )
    return _case_list


def get_modules_from_xmind(xmind_file):
    #从xmind获得所有模块

    xmind_tabs = xmind_to_dict(xmind_file)
    xmind_tree = xmind_tabs[0]
    root_topic_value = xmind_tree['topic']['title']
    case_list = tree_to_case_list(xmind_tree, root_topic_value)
    _modules = list(set([_[0] for _ in case_list]))
    return _modules


def get_modules_from_csv(csv_file):
    #从csv获得所有模块

    with open(csv_file, 'r', encoding='gbk') as csvfile:
        reader = csv.reader(csvfile)
        case_list = list(reader)
    _modules = list(set([_[0] for _ in case_list[1:]]))
    return _modules


def generate_case(xmind_file, save_path):
    xmind_tabs = xmind_to_dict(xmind_file)
    xmind_tree = xmind_tabs[0]
    root_topic_value = xmind_tree['topic']['title']
    # 按用例组织excel的行
    case_list = tree_to_case_list(xmind_tree, root_topic_value)
    # 生成csv格式的测试用例
    csv_case_list = [[
        "所属模块", "相关需求", "优先级", "影响版本", "描述-前提条件",
        "用例标题", "测试步骤", "预期结果", "用例类型", "适用阶段"
    ]]
    csv_case_list.extend(case_list)
    # 将用例写入csv文件
    with open(save_path, 'w', newline='', encoding='gbk') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerows(csv_case_list)
        print('用例xmind已成功导出为csv文件，不包含模块id')


if __name__ == '__main__':
    xmind_file = sys.argv[1]
    target_path = xmind_file + '.csv'
    if xmind_file[-6:] == '.xmind' and os.path.exists(xmind_file):
        generate_case(xmind_file, save_path=target_path)
    elif xmind_file[-4:] == '.csv' and os.path.exists(xmind_file):
        target_path = xmind_file
        print('源文件为csv，将更新所属模块id……')
    else:
        print('用例xmind文件不存在：' + xmind_file)
        exit(0)
    if len(sys.argv) > 2:
        if len(sys.argv) < 5:
            print('同步到禅道需要额外参数：禅道项目名称 禅道账号 禅道密码')
            exit(0)
        else:
            ligeit_product_name = sys.argv[2]
            zentao_account = sys.argv[3]
            zentao_password = sys.argv[4]
            # 创建模块
            case_modules = get_modules_from_csv(target_path)
            zentao_user = ZentaoSession()
            zentao_user.login(zentao_account, zentao_password)
            zentao_user.create_case_modules(case_modules, ligeit_product_name)
            # 更新用例csv
            zentao_user.update_csv_case_module_id(target_path, ligeit_product_name)
    else:
        print('只有1个参数，不进行自动导入系统操作')
