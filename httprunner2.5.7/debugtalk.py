# -*- coding: utf-8 -*-

import json
import base64

from Crypto.Cipher import AES
from Crypto.PublicKey import RSA
from Crypto.Cipher import PKCS1_v1_5


# 返回加密的登录账号密码
def hw_login_rsakey(username, password, index=0, channel=""):
    """

    Args:
        username:用户名
        password：密码
        channel：产品端（完美运营后台：op,店铺系统：store,商城：无）
        index:0或1（int）(0:返回encrypt_data,1:返回encrypt_key)

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
    username = str(username)
    password = str(password)
    index = int(index)
    channel = str(channel)

    if channel == "store":
        username_password_dic = {"password": password, "grant_type": "password",
                                 "auth_type": "store", "username": username}
        username_password_str = json.dumps(username_password_dic)
    elif channel == "op":
        username_password_dic = {"password": password, "grant_type": "password",
                                 "auth_type": "op", "username": username}
        username_password_str = json.dumps(username_password_dic)
    else:
        username_password_dic = {"password": password, "grant_type": "password", "username": username}
        username_password_str = json.dumps(username_password_dic)

    aes = AES.new(str.encode(key_main), AES.MODE_ECB)  # 初始化加密器，ECB加密模式

    encrypt_data = str(base64.encodebytes(aes.encrypt(_add_to_16(username_password_str))),
                      encoding='utf8').replace('\n', '')  # 加密 对应参数data

    # decrypt_key = aes.decrypt(base64.decodebytes(bytes(encrypt_key, encoding='utf8'))).decode("utf8")  # 解密
    # decrypt_key = decrypt_key[:-ord(decrypt_key[-1])]  # 去除多余补位

    encrypt_key = _encrypt(rsakey, key_main)  # 对应参数key
    if int(index) == 0:
        return encrypt_data
    else:
        return encrypt_key


# setup_hooks测试函数
def hw_setup(content):
    print("setup_hooks:{}".format(content))


# teardown_hooks测试函数
def hw_teardown(content):
    print("teardown_hooks:{}".format(content))


