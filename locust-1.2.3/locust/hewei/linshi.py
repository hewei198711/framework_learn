import csv
import io
import json
import os
import math
from locust.user.wait_time import between
import requests
import queue
import base64
import logging
from json import JSONDecodeError

from locust import HttpUser, TaskSet, task, LoadTestShape, events
from locust.contrib.fasthttp import FastHttpUser
from Crypto.Cipher import AES
from Crypto.PublicKey import RSA
from Crypto.Cipher import PKCS1_v1_5


def login_rsakey(data):
    """

    Args:
        data:{"username": "3000003173", "password": "003173", "grant_type": "password"}

    Returns:
        encrypt_key: dPfTkBjQAlroNpThQvUEPO5oCy86OSBNwt+tUeajgJPr57iCLpjw609LmUBHKwJDXmE5Y8o9n9D
        fERjQL9LJm3IK4ERx0FbZPZtzR6lV1Zg=

        encrypt_data:FqZnLuqWouWZOB6/DMCYqzf5u6SPtQPRSyyLpDbTATtxYIiv46Sd5OoZILv3QdIdpDz6nOyoCMbp
        ++XFtB1L2znn+TPF5oZn4KYJxDTTV7dv9yWToAf77od13GSVxykOVpEYjfDO54e8BAEmGowa5xC7yt6DpV97aGd02We/jWM=

    """

    def _add_to_16(username_password_str):
        """补足字符串长度为16的倍数"""
        while len(username_password_str) % 16 != 0:
            username_password_str += (16 - len(username_password_str) % 16) * chr(16 - len(username_password_str) % 16)
        return str.encode(username_password_str)  # 返回bytes

    def _handle_pub_key(rsakey):
        """
        处理rsa公钥
        公钥格式pem，处理成以-----BEGIN PUBLIC KEY-----开头，-----END PUBLIC KEY-----结尾的格式
        :param key:pem格式的公钥，无-----BEGIN PUBLIC KEY-----开头，-----END PUBLIC KEY-----结尾
        :return:
        """
        start = '-----BEGIN PUBLIC KEY-----\n'
        end = '-----END PUBLIC KEY-----'
        result = ''
        # 分割key，每64位长度换一行
        divide = int(len(rsakey) / 64)
        # divide = divide if (divide > 0) else divide+1
        line = divide if (len(rsakey) % 64 == 0) else divide + 1
        for i in range(line):
            result += rsakey[i * 64:(i + 1) * 64] + '\n'
        result = start + result + end
        return result

    def _encrypt(rsakey, key_main):
        """
        ras 加密[rsa公钥加密]
        :param key: 无BEGIN PUBLIC KEY头END PUBLIC KEY尾的pem格式key
        :param key_main:待加密内容
        :return:
        """
        pub_key = _handle_pub_key(rsakey)
        pub = RSA.import_key(pub_key)  # 读取公钥
        cipher = PKCS1_v1_5.new(pub)
        encrypt_bytes = cipher.encrypt(key_main.encode(encoding='utf-8'))  # 对账号密码组成的字符串加密
        result = base64.b64encode(encrypt_bytes)  # 对加密后的账号密码base64加密
        result = str(result, encoding='utf-8')
        return result

    key_main = "HFLkbvwm015UkdrD"
    rsakey = 'MIGfMA0GCSqGSIb3DQEBAQUAA4GNADCBiQKBgQDf3n7GvYCjevA+JEnMQHfxDX/ePSv' \
             'iRR2C2tsNSVyuTm6TfaP/HLzNbAO0kK+52nr2HO2LzsSd+a98V4n5npYDWPqbswXzKLj73k' \
             'BlBI0P6Uf3uygCAZtfd9qkAn0DkgGpVw1VtCb33svBkaQinOYB550OygDM1vemuQYq11E/mQIDAQAB'

    data = json.dumps(data)

    aes = AES.new(str.encode(key_main), AES.MODE_ECB)  # 初始化加密器，ECB加密模式
    # 加密 对应参数data
    encrypt_data = str(base64.encodebytes(aes.encrypt(_add_to_16(data))), encoding='utf8').replace('\n', '')
    # 解密 对应参数data
    decrypt_datat = aes.decrypt(base64.decodebytes(bytes(encrypt_data, encoding='utf8'))).decode("utf8")  # 解密
    decrypt_data = decrypt_datat[:-ord(decrypt_datat[-1])]  # 去除多余补位
    # 对应参数key
    encrypt_key = _encrypt(rsakey, key_main)

    return {"data": encrypt_data, "key": encrypt_key}
