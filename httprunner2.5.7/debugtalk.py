# -*- coding: utf-8 -*-

import json
import base64

from Crypto.Cipher import AES
from Crypto.PublicKey import RSA
from Crypto.Cipher import PKCS1_v1_5



def hw_login_rsakey(username, password, index=0, channel=""):

    def _add_to_16(username_password_str):
        while len(username_password_str) % 16 != 0:
            username_password_str += (16 - len(username_password_str) % 16) * chr(16 - len(username_password_str) % 16)
        return str.encode(username_password_str)

    def _handle_pub_key(rsakey):

        start = '-----BEGIN PUBLIC KEY-----\n'
        end = '-----END PUBLIC KEY-----'
        result = ''

        divide = int(len(rsakey) / 64)
        line = divide if (len(rsakey) % 64 == 0) else divide + 1
        for i in range(line):
            result += rsakey[i * 64:(i + 1) * 64] + '\n'
        result = start + result + end
        return result

    def _encrypt(rsakey, key_main):
        pub_key = _handle_pub_key(rsakey)
        pub = RSA.import_key(pub_key)
        cipher = PKCS1_v1_5.new(pub)
        encrypt_bytes = cipher.encrypt(key_main.encode(encoding='utf-8'))
        result = base64.b64encode(encrypt_bytes) 
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

    aes = AES.new(str.encode(key_main), AES.MODE_ECB)

    encrypt_data = str(base64.encodebytes(aes.encrypt(_add_to_16(username_password_str))),
                      encoding='utf8').replace('\n', '')


    encrypt_key = _encrypt(rsakey, key_main)
    if int(index) == 0:
        return encrypt_data
    else:
        return encrypt_key


def hw_setup(content):
    print("setup_hooks:{}".format(content))


def hw_teardown(content):
    print("teardown_hooks:{}".format(content))


