#!/usr/bin/env python3
# -*- coding:utf-8 -*-
'''
@Author:yuping
@time: 2020/10/14 9:30
'''


import xlwt
from xmindparser import xmind_to_dict


def resolvePath(dict,lists,title):
    # title去除首尾空格
    title = title.strip()
    # 如果title是空字符串，则直接获取value
    if len(title) == 0:
        concatTitle = dict['title'].strip()
    else:
        concatTitle = title + '\t' + dict['title'].strip()
    if dict.__contains__('topics')==False:
        lists.append(concatTitle)
    else:
         for d in dict['topics']:
            resolvePath(d,lists,concatTitle)



def xmind_cat( list ,excelname):
    print(f'list是{list}')

    f = xlwt.Workbook()
    # 生成excel文件，单sheet，sheet名为：sheet1
    sheet = f.add_sheet('业务功能点' , cell_overwrite_ok=True)

    row0 = ['序号', '场景', '测试点']
    # 生成第一行中固定表头内容
    for i in range(0, len(row0)):
       sheet.write(0, i, row0[i])

    # 增量索引
    index = 0

    for h in range(0,len(list)):
        lists = []
        resolvePath(list[h], lists, '')
        # print('\n'.join(lists))
        # print(len(lists))
        print(lists)

        for j in range(0, len(lists)):
            lists[j] = lists[j].split('\t')
            print(lists[j])
            # print(f'这是lists[j]长度{len(lists[j])}')

            for n in range(0, len(lists[j])):
                print(lists[j][n])
                # 第一列的序号
                sheet.write(j+index+1, 0, j+index+1)

                sheet.write(j+index+1, n+1, lists[j][n])
                # 表头中的“步骤1”-“步骤n”
                if n>= 2 :
                    sheet.write(0, n+1, '步骤'+str(n-1))

        # 遍历结束lists，给增量索引赋值，跳出for j循环，开始for h循环
        if j == len(lists) - 1:
            index += len(lists)
    f.save(excelname)



def maintest( filename):
    out = xmind_to_dict(filename)
    excelname = filename.split('/')[-1].split('.')[0] + '.xls'
    xmind_cat(out[0]['topic']['topics'],excelname)



if __name__ == '__main__':
    filename = 'D:\hewei\locust项目\locust-1.2.3\油葱商城-2.3.1.xmind'
    maintest(filename)
