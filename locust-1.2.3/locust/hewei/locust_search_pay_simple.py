# -*- coding: utf-8 -*-
"""
云商搜索商品，直接购买，自购，提交订单，钱包支付全流程场景
注意：云商必须有非取消资格的服务中心，完美钱包必须金钱充足，且设置免密支付

/mobile/product/search  搜索商品（要）

/mobile/order/carts/all  获取购物车全部列表
/mobile/active/getPromotionProductInfo  获活动商品详情以及已购买数量
/mobile/product/getProductDetail  商品详情（要）
/mobile/myShareAndFavorite/whetherAddFavPro  判断该商品是否被此会员收藏

/mobile/product/getStockInfo  查询商品库存（要）
/mobile/order/carts/hasStore  云商/微店是否已开通服务中心（要）
/mobile/order/before/thrivingHistoryList  查询代客下单搜索历史记录（要）
/mobile/order/carts/canBuy  根据用户卡号查询购买信息（要）
/mobile/order/before/addThrivingHistory  新增代客下单搜索历史记录（要）

/mobile/personalInfo/getRegInfosByParentCode  通过传parentCode获得相应的区域信息，省的parentCode默认为0
/mobile/order/carts/toSettlement  选择商品去结算（要）
/mobile/order/carts/getCartProductNum  获取购物车产品数量和选中结算产品数量
/mobile/order/checkout-params/getWebSearchStoreList  WEB搜索服务中心
/mobile/order/carts/getCouponList  获取选中结算分组的可用和不可用优惠券列表（要）
/mobile/order/carts/getGiftList  获取电子礼券列表（要）
/mobile/order/carts/getFreightList  获取运费补贴券券列表（要）
/mobile/wallet/getDetail  获取钱包首页相关信息（要）

/mobile/trade/orderCommit  提交订单（要）
/mobile/orderInfo/getOrderInfo  通过订单号查询客户端订单信息（要）
/mobile/wallet/queryPasswordExist  是否设置了支付密码（要）
/mobile/payment/getPayMethod  获取支付方式（要）

/mobile/payment/associationPay  组合支付,【适用于云商,微店（云+）,云商/微店的子账号,店员】 当钱包可用余额足够支付,二选一，
                                钱包支付或者第三方支付；当钱包可用余额不足以支付，选择钱包+第三方。店员需具备支付权限
/mobile/payment/queryWalletPayOrder  查询支付成功信息

"""

import csv
import io
import json
import os
import requests
import queue
import base64

from locust import HttpUser, TaskSet, task, SequentialTaskSet
from Crypto.Cipher import AES
from Crypto.PublicKey import RSA
from Crypto.Cipher import PKCS1_v1_5


def base_path(path="locustfiles"):
    """获取目录locust_ucong的根地址"""
    file_path = os.path.abspath(os.path.dirname(__file__))
    index = file_path.index(path)
    base_path = file_path[:index]
    return base_path


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


class SearchPay(SequentialTaskSet):

    def __init__(self, parent):
        super().__init__(parent)
        self.access_token = ""
        self.userid = ""
        self.cardno = ""  # 开单人会员卡
        self.store = ""  # 开单人所属服务中心
        self.product = {}  # 产品信息
        self.price = {}
        self.orderno = ""  # 订单号
        self.totalamount = None  # 实付金额
        self.payorderno = ""  # 支付流水

    def on_start(self):
        """登录接口，要求不同用户不能同时登录同一个账户，但是账户可以循环登录"""
        data_dict = {}
        try:
            data_dict = self.user.user_data_queue.get()  # 取出一组username+password
            # print("调试：login with username: {}, password: {}".format(data_dict["username"], data_dict["password"]))
        except queue.Empty:
            print("accout data run out, test ended.")
            exit(0)

        data = login_rsakey(data_dict)
        headers = {"Authorization": "Basic cG9ydGFsX2FwcDpwZXJmZWN0X3BvcnRhbA=="}

        # 使用with句式，方便定制断言
        with self.client.post(url="/login", data=data, headers=headers, catch_response=True) as rsp:
            if rsp.json()["code"] == 200:
                # 提取后面接口需要用到的参数，放到类属性里面
                self.access_token = rsp.json()["data"]["access_token"]
                self.userid = rsp.json()["data"]["userId"]
                self.cardno = rsp.json()["data"]["cardNo"]
                self.store = rsp.json()["data"]["username"]
                rsp.success()
            else:
                rsp.failure("status_code != 200")

        # 已经取出这组username+password，再次放到队列中（如果不能循环取数，如支付订单，则不要放回队列中）
        # self.user.user_data_queue.put_nowait(data_dict)

    @task()
    def search(self):
        """
        搜索商品
        :return:
        {
          "code": 200,
          "message": "操作成功",
          "data": {
            "pageNum": 1,
            "pageSize": 12,
            "totalPage": 1,
            "total": 1,
            "list": [
              {
                "productId": "391",  # 产品id
                "serialNo": "AF23118",  # 产品编码
                "title": "荟新芦荟滋养护色润发乳",  # 产品名称
                "catalogTitle": "保洁用品及个人护理品",  # 产品分类
                "catalogId": "2",  # 分类id
                "showList": [  # 前端分类集合
                  {
                    "showId": "2",  # 前端分类id
                    "title": "保洁用品"  # 分类名
                  }
                ],
                "retailPrice": 39,  # 产品售价
                "groupPrice": 30,  # 单位团购价
                "pv": 30,
                "securityPrice": 13,  # 押货价(订货价)
                "imgUrl": "https://uc.oss.perfect99.com/mall-center-product/20210325114314STKTS.png",  # 产品图片
                "orderType": 1,  # 订货类型 1-产品订货 2-资料订货 3-定制品订货
                "isExchangeProduct": 0,
                "productType": 1
              }
            ]
          }
        }
        """
        url = "/mobile/product/search"
        headers = {
            "Authorization": "bearer " + self.access_token,
            "Content-Type": "application/json;charset=UTF-8"
        }
        data = {
            "catalogIds": [],  # 分类id集合
            "brandIds": [],  # 品牌id集合
            "tagIds": [],  # 标签id集合
            "pageNum": 1,
            "pageSize": 12,
            "keyword": "荟新芦荟滋养护色润发乳"  # 搜索关键字--产品名称或产品编码
        }
        data = json.dumps(data)
        with self.client.post(url=url, headers=headers, data=data, catch_response=True) as r:
            if r.json()["code"] == 200:
                self.product = r.json()["data"]["list"][0]
                r.success()
            else:
                r.failure("code != 200")

    @task()
    def get_product_detail(self):
        """
        商品详情
        :return
        {
          "code": 200,
          "message": "操作成功",
          "data": {
            "productId": "391",
            "serialNo": "AF23118",
            "title": "荟新芦荟滋养护色润发乳",
            "productType": 1,
            "productStatus": 7,
            "retailPrice": 39,
            "pv": 30,
            "medais": [
              {
                "mediaType": 1,
                "url": "https://uc.oss.perfect99.com/mall-center-product/20210325114314STKTS.png",
                "sort": 2
              }
            ],
            "serveContent": "1、收货时请当场验货，若商品有破损、渗漏、缺少、交付有误等问题，请立即与完美公司客服人员或分支机构联系。2、 消费者在购买产品30天内，将完好无损、具有销售价值的产品连同购货凭证一同退回，可按购货凭证价格等值换货或退款。3、若商品使用过程中怀疑出现质量问题，请立即与完美公司客服人员或分支机构联系，同时提供购货凭证及清晰的产品问题图片。4、金伟连牌净水机、宜悦牌空气净化机/器、德列宝系列（锅具、厨具）产品若消费者在使用过程中发生故障情况，请及时与完美公司客服人员或分支机构联系，具体售后服务规定详见《使用说明书》、《用户手册》。",
            "webContent": "<img src=\"https://uc.oss.perfect99.com/perfect-mall-1/prod/group1/cReMm4hf7N.jpg\" alt=\"\" /><img src=\"https://uc.oss.perfect99.com/perfect-mall-1/prod/group1/k42cEM3emZ.jpg\" alt=\"\" /><img src=\"https://uc.oss.perfect99.com/perfect-mall-1/prod/group1/WZCizXamRZ.jpg\" alt=\"\" /><img src=\"https://uc.oss.perfect99.com/perfect-mall-1/prod/group1/Zw27pDSX2S.jpg\" alt=\"\" /><img src=\"https://uc.oss.perfect99.com/perfect-mall-1/prod/group1/HYj5jCwJpX.jpg\" alt=\"\" /><img src=\"https://uc.oss.perfect99.com/perfect-mall-1/prod/group1/wYxhTe5KQf.jpg\" alt=\"\" /><img src=\"https://uc.oss.perfect99.com/perfect-mall-1/prod/group1/XrmiZ4dhQs.jpg\" alt=\"\" /><img src=\"https://uc.oss.perfect99.com/perfect-mall-1/prod/group1/CGK72Y7fJb.jpg\" alt=\"\" /><img src=\"https://uc.oss.perfect99.com/perfect-mall-1/prod/group1/3G85ikWjye.jpg\" alt=\"\" /><img src=\"https://uc.oss.perfect99.com/perfect-mall-1/prod/group1/5PTCPdxKXT.jpg\" alt=\"\" /><img src=\"https://uc.oss.perfect99.com/perfect-mall-1/prod/group1/4mP2tKyECS.jpg\" alt=\"\" />",
            "appContent": "<img src=\"https://uc.oss.perfect99.com/perfect-mall-1/prod/group1/8fPmPQzNHt.jpg\" alt=\"\" /><img src=\"https://uc.oss.perfect99.com/perfect-mall-1/prod/group1/7j3mBrT6ca.jpg\" alt=\"\" /><img src=\"https://uc.oss.perfect99.com/perfect-mall-1/prod/group1/chpw3y4kPm.jpg\" alt=\"\" /><img src=\"https://uc.oss.perfect99.com/perfect-mall-1/prod/group1/sYMkcxMWAf.jpg\" alt=\"\" /><img src=\"https://uc.oss.perfect99.com/perfect-mall-1/prod/group1/X33KWhiYQG.jpg\" alt=\"\" /><img src=\"https://uc.oss.perfect99.com/perfect-mall-1/prod/group1/AXaNJS44wj.jpg\" alt=\"\" /><img src=\"https://uc.oss.perfect99.com/perfect-mall-1/prod/group1/fmDF7ztPxk.jpg\" alt=\"\" /><img src=\"https://uc.oss.perfect99.com/perfect-mall-1/prod/group1/6pFR6KacpR.jpg\" alt=\"\" /><img src=\"https://uc.oss.perfect99.com/perfect-mall-1/prod/group1/RxnEiTWb72.jpg\" alt=\"\" /><img src=\"https://uc.oss.perfect99.com/perfect-mall-1/prod/group1/MGHtwWkjR4.jpg\" alt=\"\" /><img src=\"https://uc.oss.perfect99.com/perfect-mall-1/prod/group1/48irdiTPhe.jpg\" alt=\"\" />",
            "customList": null,
            "bundleList": null,
            "releList": [
              {
                "productId": "992",
                "title": "荟新洗护四件套",
                "serialNo": "AFSG1804",
                "imgUrl": "https://uc.oss.perfect99.com/mall-center-product/202103260952322h6yX.png",
                "retailPrice": 168,
                "discountPrice": 28,
                "bundleList": [
                  {
                    "productId": "391",
                    "title": "荟新芦荟滋养护色润发乳",
                    "serialNo": "AF23118",
                    "productType": "1",
                    "imgUrl": "https://uc.oss.perfect99.com/mall-center-product/20210325114314STKTS.png",
                    "retailPrice": 39,
                    "amount": 1,
                    "isCommodity": 1
                  },
                  {
                    "productId": "392",
                    "title": "荟新芦荟滋养护色洗发露",
                    "serialNo": "AF13118",
                    "productType": "1",
                    "imgUrl": "https://uc.oss.perfect99.com/mall-center-product/20210325113915UgRH6.png",
                    "retailPrice": 69,
                    "amount": 1,
                    "isCommodity": null
                  },
                  {
                    "productId": "142",
                    "title": "荟新芦荟沐浴露",
                    "serialNo": "SG18",
                    "productType": "1",
                    "imgUrl": "https://uc.oss.perfect99.com/perfect-mall-1/prod/home/cz8eaKFDwY.png",
                    "retailPrice": 69,
                    "amount": 1,
                    "isCommodity": null
                  },
                  {
                    "productId": "389",
                    "title": "荟新动感定型啫喱",
                    "serialNo": "AF30118",
                    "productType": "1",
                    "imgUrl": "https://uc.oss.perfect99.com/mall-center-product/20210326092830u0aEK.png",
                    "retailPrice": 19,
                    "amount": 1,
                    "isCommodity": null
                  }
                ]
              }
            ],
            "recoList": [
              {
                "productId": "24",
                "title": "芦荟胶礼盒",
                "serialNo": "AG2",
                "imgUrl": "https://uc.oss.perfect99.com/mall-center-product/20210325114748vICno.png",
                "retailPrice": 70,
                "pv": 59
              },
              {
                "productId": "142",
                "title": "荟新芦荟沐浴露",
                "serialNo": "SG18",
                "imgUrl": "https://uc.oss.perfect99.com/perfect-mall-1/prod/home/cz8eaKFDwY.png",
                "retailPrice": 69,
                "pv": 55
              },
              {
                "productId": "392",
                "title": "荟新芦荟滋养护色洗发露",
                "serialNo": "AF13118",
                "imgUrl": "https://uc.oss.perfect99.com/mall-center-product/20210325113915UgRH6.png",
                "retailPrice": 69,
                "pv": 55
              },
              {
                "productId": "329",
                "title": "荟亮芦荟牙膏套装",
                "serialNo": "TPP18",
                "imgUrl": "https://uc.oss.perfect99.com/perfect-mall-1/prod/home/AEED2fR5bS.png",
                "retailPrice": 68,
                "pv": 53
              },
              {
                "productId": "102",
                "title": "荟净芦荟餐具洗洁精",
                "serialNo": "DW18",
                "imgUrl": "https://uc.oss.perfect99.com/perfect-mall-1/prod/home/xZN3a67NJR.png",
                "retailPrice": 50,
                "pv": 40
              }
            ],
            "originalPrice": 39,
            "reduPrice": null,
            "stockMax": null,
            "stockRest": "-344477",
            "stockType": 2,
            "isStopSale": 0,
            "isExchangeProduct": 0,
            "attrs": "{\"产地\":\"\"}",
            "attrList": [],
            "orderType": 1
          }
        }
        """
        url = "/mobile/product/getProductDetail"
        headers = {"Authorization": "bearer " + self.access_token}
        params = {"productCode": self.product["serialNo"]}
        with self.client.get(url=url, headers=headers, params=params, name="/mobile/product/getProductDetail",
                             catch_response=True) as r:
            if r.json()["code"] == 200:
                r.success()
            else:
                r.failure("code != 200")

    @task()
    def get_stock_info(self):
        """
        查询商品库存
        :return
        {
          "code": 200,
          "message": "操作成功",
          "data": {
            "id": "391",
            "stockId": "17",
            "serialNo": "AF23118",
            "title": "荟新芦荟滋养护色润发乳",
            "saleCompanyId": "2",
            "saleCompanyTitle": "完美中国",
            "catalogId": "2",
            "catalogTitle": "保洁用品及个人护理品",
            "shippingId": "1217978678543324234",
            "shippingTpl": "按订单金额收取运费",
            "productType": 1,
            "orderType": 1,
            "pv": 30,
            "retailPrice": 39,
            "securityPrice": 13,
            "picUrls": [
              "https://uc.oss.perfect99.com/mall-center-product/20210325114314STKTS.png"
            ],
            "isConsumeStock": 0,
            "isStopSale": 0,
            "isExchangeProduct": 0,
            "productStatus": 7,
            "updateTime": "1619515209000",
            "restSaleQuota": "-344477",
            "maxSaleQuota": null,
            "stockType": 2,
            "meterUnit": "支",
            "packing": "260ml/支",
            "versionId": "3942"
          }
        }
        """
        url = "/mobile/product/getStockInfo"
        headers = {"Authorization": "bearer " + self.access_token}
        params = {"serialNo": self.product["serialNo"]}  # 产品编码
        with self.client.get(url=url, headers=headers, params=params, name="/mobile/product/getStockInfo",
                             catch_response=True) as r:
            if r.json()["code"] == 200:
                r.success()
            else:
                r.failure("code != 200")

    @task()
    def has_store(self):
        """
        云商/微店是否已开通服务中心
        :return
        {
          "code": 200,
          "message": "操作成功",
          "data": null
        }
        """
        url = "/mobile/order/carts/hasStore"
        headers = {"Authorization": "bearer " + self.access_token}
        with self.client.get(url=url, headers=headers, catch_response=True) as r:
            if r.json()["code"] == 200:
                r.success()
            else:
                r.failure("code != 200")

    @task()
    def thriving_history_list(self):
        """
        查询代客下单搜索历史记录
        :return:
        {
          "code": 200,
          "message": "操作成功",
          "data": [
            {
              "id": "77",
              "creatorCard": "3000003166",
              "cardNo": "3000003185",
              "realname": "何伟二十九号",
              "createTime": 1619494798000,
              "updateTime": null,
              "version": null
            },
            {
              "id": "76",
              "creatorCard": "3000003166",
              "cardNo": "3000003163",
              "realname": "张萧萧",
              "createTime": 1619494773000,
              "updateTime": null,
              "version": null
            },
            {
              "id": "75",
              "creatorCard": "3000003166",
              "cardNo": "3000003154",
              "realname": "完美测试二号",
              "createTime": 1619494725000,
              "updateTime": null,
              "version": null
            },
            {
              "id": "59",
              "creatorCard": "3000003166",
              "cardNo": "3000003166",
              "realname": "何伟十九号",
              "createTime": 1619425498000,
              "updateTime": null,
              "version": null
            }
          ]
        }
        """
        url = "/mobile/order/before/thrivingHistoryList"
        headers = {
            "Authorization": "bearer " + self.access_token,
            "Content-Type": "application/json;charset=UTF-8"
        }
        data = {
            "cardNo": "",  # 开单人卡号
            "from": "",
            "pageNum": 1,
            "pageSize": 99999
        }
        data = json.dumps(data)
        with self.client.post(url=url, headers=headers, data=data, catch_response=True) as r:
            if r.json()["code"] == 200:
                r.success()
            else:
                r.failure("code != 200")

    @task()
    def can_buy(self):
        """
        根据用户卡号查询购买信息
        :return
        {
          "code": 200,
          "message": "操作成功",
          "data": {
            "memberId": "1269746690482701867",
            "cardNo": "3000003166",
            "mobile": "18928790019",
            "nickname": "3000003166",
            "memberStatus": 0,
            "realname": "何伟十九号",
            "limitNumber": -1,
            "quotaNumber": -1,
            "pv": 505,
            "isFiveStar": 0,
            "cardStatus": 0,
            "cancelDate": null
          }
        }
        """
        url = "/mobile/order/carts/canBuy"
        headers = {
            "Authorization": "bearer " + self.access_token,
            "Content-Type": "application/json;text/plain,*/*"
        }
        data = {
            "cardNo": self.cardno,  # 用户卡号
            "serialNo": self.product["serialNo"]  # 商品编码
        }
        data = json.dumps(data)
        with self.client.post(url=url, headers=headers, data=data, catch_response=True) as r:
            if r.json()["code"] == 200:
                r.success()

    @task()
    def add_thriving_history(self):
        """
        新增代客下单搜索历史记录
        :return
        {
          "code": 200,
          "message": "操作成功",
          "data": "新增成功"
        }
        """
        url = "/mobile/order/before/addThrivingHistory"
        headers = {"Authorization": "bearer " + self.access_token}
        params = {"cardNo": self.cardno}
        with self.client.post(url=url, headers=headers, params=params, name="/mobile/order/before/addThrivingHistory",
                              catch_response=True) as r:
            if r.json()["code"] == 200:
                r.success()
            else:
                r.failure("code != 200")

    @task()
    def get_coupon_list(self):
        """
        获取选中结算分组的可用和不可用优惠券列表
        :return
        {
          "code": 200,
          "message": "操作成功",
          "data": {
            "memberId": null,
            "availableList": null,
            "notAvailableList": null
          }
        }
        """
        url = "/mobile/order/carts/getCouponList"
        headers = {
            "Authorization": "bearer " + self.access_token,
            "Content-Type": "application/json;charset=UTF-8"
        }
        data = {
            "customerCard": self.cardno,  # 开单人卡号
            "sourceType": 1,  # 1(立即购买/快速购货)，2(购物车提交),3(结算前销售调整)
            "productList": [
                {
                    "releList": [],
                    "imgUrl": self.product["imgUrl"],
                    "title": self.product["title"],
                    "serialNo": self.product["serialNo"],
                    "retailPrice": self.product["retailPrice"],
                    "quantity": 1,
                    "pv": self.product["pv"],
                    "productType": self.product["productType"],
                    "number": 1
                }
            ]
        }
        data = json.dumps(data)
        with self.client.post(url=url, headers=headers, data=data, catch_response=True) as r:
            if r.json()["code"] == 200:
                r.success()
            else:
                r.failure("code != 200")

    @task()
    def get_gift_list(self):
        """
        获取电子礼券列表
        :return
        {
          "code": 200,
          "message": "操作成功",
          "data": []
        }
        """
        url = "/mobile/order/carts/getGiftList"
        headers = {
            "Authorization": "bearer " + self.access_token,
            "Content-Type": "application/json;charset=UTF-8"
        }
        data = {
          "customerCard": self.cardno,  # 开单人卡号
          "sourceType": 1,  # 1(立即购买/快速购货)，2(购物车提交),3(结算前销售调整)
          "productList": [
                {
                    "releList": [],
                    "imgUrl": self.product["imgUrl"],
                    "title": self.product["title"],
                    "serialNo": self.product["serialNo"],  # 产品编码
                    "retailPrice": self.product["retailPrice"],  # 产品价格
                    "quantity": 1,  # 数量
                    "pv": self.product["pv"],
                    "productType": self.product["productType"],
                    "number": 1  # 换购商品数量
                }
          ]
        }
        data = json.dumps(data)
        with self.client.post(url=url, headers=headers, data=data, catch_response=True) as r:
            if r.json()["code"] == 200:
                r.success()
            else:
                r.failure("code != 200")

    @task()
    def get_freight_list(self):
        """
        获取运费补贴券券列表
        :return
        {
          "code": 200,
          "message": "操作成功",
          "data": []
        }
        """
        url = "/mobile/order/carts/getFreightList"
        headers = {
            "Authorization": "bearer " + self.access_token,
            "Content-Type": "application/json;charset=UTF-8"
        }
        data = {
          "customerCard": self.cardno,  # 开单人卡号
          "sourceType": 1,  # 1(立即购买/快速购货)，2(购物车提交),3(结算前销售调整)
          "productList": [
                {
                    "releList": [],
                    "imgUrl": self.product["imgUrl"],
                    "title": self.product["title"],
                    "serialNo": self.product["serialNo"],  # 产品编码
                    "retailPrice": self.product["retailPrice"],  # 产品价格
                    "quantity": 1,  # 数量
                    "pv": self.product["pv"],
                    "productType": self.product["productType"],
                    "number": 1  # 换购商品数量
                }
          ]
        }
        data = json.dumps(data)
        with self.client.post(url=url, headers=headers, data=data, catch_response=True) as r:
            if r.json()["code"] == 200:
                r.success()
            else:
                r.failure("code != 200")

    @task()
    def to_settlement(self):
        """
        选择商品去结算
        :return
        {
          "code": 200,
          "message": "操作成功",
          "data": {
            "saleCompanyId": "2",
            "saleCompanyTitle": "完美中国",
            "expressType": 1,
            "productList": [
              {
                "checked": 1,
                "saleCompanyId": "2",
                "saleCompanyTitle": "完美中国",
                "productId": "391",
                "serialNo": "AF23118",
                "catalogId": "2",
                "title": "荟新芦荟滋养护色润发乳",
                "shippingId": "1217978678543324234",
                "shippingTpl": "按订单金额收取运费",
                "productType": 1,
                "quantity": 1,
                "pv": 30,
                "picture": "https://uc.oss.perfect99.com/mall-center-product/20210325114314STKTS.png",
                "retailPrice": 39,
                "originalPrice": null,
                "subtotal": 39,
                "pvSubtotal": 30,
                "expressAmount": null,
                "isActivity": 0,
                "limitBuy": 0,
                "limitNumber": null,
                "availableNumber": null,
                "addCartTime": 1619525442438,
                "isConsumeStock": 0,
                "availableStock": -344477,
                "invalid": 0,
                "lastModify": "1616651866000",
                "isExchange": 0,
                "exchangeSize": null,
                "meterUnit": "支",
                "packing": "260ml/支",
                "versionId": "3942",
                "orderType": 1,
                "isExchangeProduct": 0,
                "exchangeList": []
              }
            ],
            "customerMemberId": "1269746690482701867",
            "customer": "何伟十九号",
            "customerCard": "3000003166",
            "customerType": 3,
            "customerPhone": "18928790019",
            "price": {
              "totalPrice": 37,
              "productPrice": 39,  # 商品价格=单价*数量
              "expressAmount": 0,
              "pv": 30,
              "returnRate": 0.06,
              "returnAmount": 2,
              "cumulativePv": 535,
              "discountAmount": 0,
              "payPrice": 37,
              "couponAmount": 0,
              "giftCouponAmount": 0,
              "freightCouponAmount": 0,
              "useCouponList": [],
              "useGiftList": [],
              "useFreightList": []
            },
            "addCartTime": 1619525442451,
            "invalid": 0,
            "checked": 1,
            "sharerId": null,
            "sourceType": 1,
            "checkoutVO": {
              "expressType": 1,
              "addressId": null,
              "storeCode": "942582",
              "remark": null,
              "clientType": null,
              "orderInvoiceVo": null,
              "ownerId": null,
              "storeVO": {
                "id": "1265814679767408783",
                "phone": null,
                "shopkeeperId": "1269746690482701867",
                "shopkeeperNo": null,
                "name": "何伟十九号的总店",
                "leaderId": "1235484457239250080",
                "leaderNo": "3000003166",
                "leaderName": "何伟十九号",
                "email": null,
                "fax": null,
                "zipCode": null,
                "shopType": 1,
                "remarks": "",
                "isMainShop": 1,
                "level": 1,
                "companyCode": "02000",
                "companyName": "完美（中国）有限公司广东分公司",
                "openDate": null,
                "ratifyDate": 1618329600000,
                "decorationInfo": null,
                "extraInfo": null,
                "code": "942582",
                "isServiceShop": null,
                "isSignContract": null,
                "provinceCode": "440000000000",
                "provinceName": "广东省",
                "cityCode": "440100000000",
                "cityName": "广州市",
                "deliveryInfo": "广东省 广州市 海珠区  广州市海珠区同创汇13号",
                "shopStatus": 0,
                "permission": "1,2,3,4,5",
                "areaCode": "440105000000",
                "areaName": "海珠区",
                "streetName": "",
                "streetCode": "",
                "detailAddress": "广州市海珠区同创汇13号",
                "lng": "113.314681",
                "lat": "23.100309",
                "del": 0,
                "ucongNo": null,
                "disqualified": false,
                "disableLogin": false,
                "selfOrder": true
              },
              "isStock": 1,
              "addressVO": null,
              "ownerVO": null
            },
            "recommendMaxCoupon": null,
            "isFiveStar": 0,
            "cardStatus": 0,
            "cancelDate": null
          }
        }
        """
        url = "/mobile/order/carts/toSettlement"
        headers = {
            "Authorization": "bearer " + self.access_token,
            "Content-Type": "application/json;charset=UTF-8"
        }
        data = {
          "addressId": None,
          "customerCard": self.cardno,  # 开单人
          "customerId": self.userid,  # 开单人ID
          "productList": [  # 购买产品信息
            {
              "releList": None,
              "imgUrl": self.product["imgUrl"],
              "title": self.product["title"],
              "serialNo":  self.product["serialNo"],
              "retailPrice":  self.product["retailPrice"],
              "quantity": 1,  # 购买数量
              "pv": self.product["pv"],
              "productType":  self.product["productType"],  # 商品类型 1-商品，2-定制商品,3-组合商品
              "number": 1  # 换购商品数量
            }
          ],
          "orderInvoice": None,
          "couponList": [],
          "giftList": [],
          "freightList": [],
          "storeCode": None,
          "ownerId": "",
          "pv": "",
          "remarks": "",
          "sharerId": None,
          "sourceType": 1  # 1(立即购买/快速购货)，2(购物车提交),3(结算前销售调整),4(定制商品购买),5(辅销品购买),6(旧版商品购买)
        }
        data = json.dumps(data)
        with self.client.post(url=url, headers=headers, data=data, catch_response=True) as r:
            if r.json()["code"] == 200:
                self.price = r.json()["data"]["price"]
                r.success()
            else:
                r.failure("status_code != 200")

    @task()
    def get_detail(self):
        """
        获取钱包首页相关信息
        :return
        {
          "code": 200,
          "message": "操作成功",
          "data": {
            "actualBalance": 997919,
            "availableBalance": 997919,
            "frozenAmount": 0,
            "rechargeAmount": 0,
            "withdrawableAmount": 997919,
            "creditAmount": 0,
            "rechargeEnable": false,
            "withdrawEnable": true,
            "passwordFlag": 1,
            "couponEnable": false,
            "freightEnable": false,
            "creditAdjustedEnable": false,
            "increaseStartTime": 1638288000000,
            "increaseEndTime": 1638720000000,
            "reduceTime": 1638288000000,
            "drawSummaryAmt": 0,
            "companyNo": "02000",
            "companyName": "广东分公司"
          }
        }
        """
        url = "/mobile/wallet/getDetail"
        headers = {
            "Authorization": "bearer " + self.access_token,
            "Content-Type": "application/json;charset=UTF-8"
        }
        with self.client.get(url=url, headers=headers, catch_response=True) as r:
            if r.json()["code"] == 200:
                r.success()
            else:
                r.failure("code != 200")

    @task()
    def order_commit(self):
        """
        提交订单
        :return
        {
          "code": 200,
          "message": "操作成功",
          "data": {
            "orderNo": "SG942582210427000009",
            "totalAmount": 37,
            "sysCancelTime": null,
            "commitTime": 1619525561883
          }
        }
        """
        url = "/mobile/trade/orderCommit"
        headers = {
            "Authorization": "bearer " + self.access_token,
            "Content-Type": "application/json;charset=UTF-8"
        }
        data = {
          "addressId": None,  # 收货地址id
          "customerCard":  self.cardno,  # 开单人卡号
          "customerId": self.userid,  # 开单人id
          "expressType": 1,  # 配送方式 1->服务中心自提 2->公司配送
          "orderAmount": self.price["productPrice"],  # 商品金额,提交订单时必传
          "productList": [  # 购买产品信息
                {
                    "releList": None,
                    "imgUrl": self.product["imgUrl"],
                    "title": self.product["title"],
                    "serialNo": self.product["serialNo"],  # 产品编码
                    "retailPrice": self.product["retailPrice"],  # 产品价格"
                    "quantity": 1,  # 数量
                    "pv": self.product["pv"],
                    "productType": self.product["productType"],
                    "number": 1  # 换购商品数量
                }
          ],
          "orderInvoice": None,  # 发票信息
          "couponList": [],  # 使用的优惠卷
          "giftList": [],  # 使用的电子礼券
          "freightList": [],  # 使用的运费补贴礼券
          "storeCode": self.store,  # 服务中心编码
          "ownerId": "",  # 送货人ID
          "pv": self.price["pv"],
          "remarks": "",  # 备注
          "returnRate": self.price["returnRate"],  # 返还比例,提交订单时必传
          "sharerId": None,  # 分享人id
          "sourceType": 1  # 1(立即购买/快速购货)，2(购物车提交),3(结算前销售调整),4(定制商品购买),5(辅销品购买),6(旧版商品购买)
        }
        data = json.dumps(data)
        with self.client.post(url=url, headers=headers, data=data, catch_response=True) as r:
            if r.json()["code"] == 200:
                self.orderno = r.json()["data"]["orderNo"]
                self.totalamount = r.json()["data"]["totalAmount"]
                r.success()
            else:
                r.failure("code != 200")

    @task()
    def get_order_info(self):
        """
        通过订单号查询客户端订单信息
        :return
        {
          "code": 200,
          "message": "操作成功",
          "data": {
            "orderNo": "SG942582210427000009",
            "orderWay": 1,
            "orderType": 1,
            "orderTypeDesc": "正常订单",
            "stockType": 2,
            "orderStatus": 1,
            "cancelReason": null,
            "orderAmount": 39,
            "totalAmount": 37,
            "giftCouponAmount": 0,
            "couponAmount": 0,
            "expressSubsidyAmount": 0,
            "returnRate": 0.06,
            "returnAmount": 2,
            "expressAmount": 0,
            "pv": 30,
            "commitTime": 1619525562000,
            "payType": null,
            "payTime": null,
            "payNo": null,
            "creatorId": "1269746690482701867",
            "creatorName": "何伟十九号",
            "creatorCard": "3000003166",
            "creatorPhone": "18928790019",
            "customerName": "何伟十九号",
            "customerCard": "3000003166",
            "customerPhone": "18928790019",
            "ownerName": null,
            "ownerCard": null,
            "ownerPhone": null,
            "receiver": "何伟十九号",
            "receiverPhone": "18928790019",
            "receiverAddress": "{\"address\":\"广州市海珠区同创汇13号\",\"city\":\"广州市\",\"cityCode\":\"440100000000\",\"district\":\"海珠区\",\"districtCode\":\"440105000000\",\"postCode\":\"null\",\"province\":\"广东省\",\"provinceCode\":\"440000000000\",\"storeCode\":\"942582\",\"storeName\":\"何伟十九号的总店\",\"storePhone\":\"\",\"street\":\"\",\"streetCode\":\"\"}",
            "isInvoice": 0,
            "grandTotalPv": 535,
            "sysCancelTime": null,
            "sysReceiveTime": null,
            "expressType": 1,
            "expressTypeDesc": "服务中心自提",
            "financeCompanyCode": "02000",
            "financeCompanyName": "完美（中国）有限公司广东分公司",
            "storeCode": "942582",
            "storeName": "何伟十九号的总店",
            "storePhone": null,
            "serviceNo": null,
            "serviceType": null,
            "orderMonth": "202104",
            "isNextMonth": false,
            "isAcrossMonth": false,
            "sysTime": 1619525562232,
            "orderProductVOList": [
              {
                "serialNo": "AF23118",
                "cusSerialNo": null,
                "title": "荟新芦荟滋养护色润发乳",
                "productType": 1,
                "orderType": 1,
                "meterUnit": "支",
                "retailPrice": 39,
                "price": null,
                "quantity": 1,
                "pv": 30,
                "picture": "https://uc.oss.perfect99.com/mall-center-product/20210325114314STKTS.png",
                "packing": "260ml/支",
                "totalPrice": 39,
                "totalPv": 30,
                "orderProductVO": null
              }
            ],
            "orderStatusChangeVOList": [
              {
                "orderStatus": 1,
                "createTime": 1619525562000
              }
            ]
          }
        }
        """
        url = "/mobile/orderInfo/getOrderInfo"
        headers = {
            "Authorization": "bearer " + self.access_token,
            "Content-Type": "application/json;charset=UTF-8"
        }
        params = {"orderNo": self.orderno}
        with self.client.get(url=url, headers=headers, name="/mobile/orderInfo/getOrderInfo", params=params,
                             catch_response=True) as r:
            if r.json()["code"] == 200:
                r.success()
            else:
                r.failure("code != 200")

    @task()
    def query_password_exist(self):
        """
        是否设置了支付密码
        :return
        {
          "code": 200,
          "message": "操作成功",
          "data": true
        }
        """
        url = "/mobile/wallet/queryPasswordExist"
        headers = {
            "Authorization": "bearer " + self.access_token,
            "Content-Type": "application/json;charset=UTF-8"
        }
        with self.client.get(url=url, headers=headers, catch_response=True) as r:
            if r.json()["code"] == 200:
                r.success()
            else:
                r.failure("code != 200")

    @task()
    def get_pay_method(self):
        """
        获取支付方式
        :return
        {
          "code": 200,
          "message": "操作成功",
          "data": [
            {
              "id": null,
              "bindName": null,
              "bindIdcard": null,
              "bankType": null,
              "payWayId": 202,
              "bankAccount": null,
              "bankName": "建设银行",
              "bankAddress": null,
              "bankBranchName": null,
              "defaultSignAccount": null,
              "maincardSpouse": null,
              "createTime": null,
              "tel": null,
              "rate": 0
            },
            {
              "id": null,
              "bindName": null,
              "bindIdcard": null,
              "bankType": null,
              "payWayId": 103,
              "bankAccount": null,
              "bankName": "银联",
              "bankAddress": null,
              "bankBranchName": null,
              "defaultSignAccount": null,
              "maincardSpouse": null,
              "createTime": null,
              "tel": null,
              "rate": 0
            },
            {
              "id": null,
              "bindName": null,
              "bindIdcard": null,
              "bankType": null,
              "payWayId": 101,
              "bankAccount": null,
              "bankName": "微信支付",
              "bankAddress": null,
              "bankBranchName": null,
              "defaultSignAccount": null,
              "maincardSpouse": null,
              "createTime": null,
              "tel": null,
              "rate": 0
            },
            {
              "id": null,
              "bindName": null,
              "bindIdcard": null,
              "bankType": null,
              "payWayId": 102,
              "bankAccount": null,
              "bankName": "支付宝支付",
              "bankAddress": null,
              "bankBranchName": null,
              "defaultSignAccount": null,
              "maincardSpouse": null,
              "createTime": null,
              "tel": null,
              "rate": 0
            }
          ]
        }
        """
        url = "/mobile/payment/getPayMethod"
        headers = {
            "Authorization": "bearer " + self.access_token,
            "Content-Type": "application/json;charset=UTF-8"
        }
        data = {
            "orderNoList": [self.orderno],  # 订单号集合
            "payType": "PC",  # 支付类型,H5、APP、PC、PROGRAM
            "sourceType": 1  # 1(立即购买/快速购货)，2(购物车提交),3(结算前销售调整) 结算前销售调整sourceType不能为空
        }
        data = json.dumps(data)
        with self.client.post(url=url, headers=headers, data=data, catch_response=True) as r:
            if r.json()["code"] == 200:
                r.success()
            else:
                r.failure("code != 200")

    @task()
    def association_pay(self):
        """
        组合支付,【适用于云商,微店（云+）,云商/微店的子账号,店员】 当钱包可用余额足够支付,二选一，钱包支付或者第三方支付；
        当钱包可用余额不足以支付，选择钱包+第三方。店员需具备支付权限
        :return
        {
          "code": 200,
          "message": "操作成功",
          "data": {
            "payOrderNo": "PM202104272013400001",
            "payInfo": null,
            "payStatus": 2
          }
        }
        """
        url = "/mobile/payment/associationPay"
        headers = {
            "Authorization": "bearer " + self.access_token,
            "Content-Type": "application/json;charset=UTF-8"
        }
        data = {
            "actualAmt": self.totalamount,  # 实付金额 税率为零时等于应付金额,不为零时,实付金额=(应付金额-钱包可用余额)*费率+应付金额
            "channelCode": 800,  # 支付渠道 支付方式 101：微信；102：支付宝；103：银联；201:工商银行 202：建设银行 204：交通银行 800:钱包支付
            "orderNoList": [self.orderno],  # 等待支付商品订单集合
            "payType": "PC",  # 支付类型,H5、APP、PC、PROGRAM
            "payableAmt": self.totalamount,  # 订单总应付金额
            "feeRate": 0,  # 手续费率
            "jumpUrl": "http://uc2-uat.perfect99.com/mall/personalCenter/myOrder",  # 支付成功前端跳转地址,微信支付必传字段信息
            "walletPassword": "",  # 钱包充值密码,非免密必传字段
            "sourceType": 1  # 1(立即购买/快速购货)，2(购物车提交),3(结算前销售调整) 结算前销售调整sourceType不能为空
        }
        data = json.dumps(data)
        with self.client.post(url=url, headers=headers, data=data, catch_response=True) as r:
            if r.json()["code"] == 200:
                self.payorderno = r.json()["data"]["payOrderNo"]
                r.success()
            else:
                r.failure("code != 200")

    @task()
    def query_wallet_pay_order(self):
        """
        查询支付成功信息
        :return
        {
          "code": 200,
          "message": "操作成功",
          "data": {
            "payNo": "PM202104272013400001",
            "payMethod": 800,
            "payMethodDesc": "完美钱包",
            "cardNo": "3000003166",
            "currency": 1,
            "totalAmount": 37,
            "payableAmount": 37,
            "actualAmount": 37,
            "walletPayAmount": 37,
            "creditPayAmount": 0,
            "feeRate": 0,
            "thirdpartyPayAmount": 0,
            "orderNos": [
              "SG942582210427000010"
            ],
            "payStatus": 1
          }
        }
        """
        url = "/mobile/payment/queryWalletPayOrder"
        headers = {
            "Authorization": "bearer " + self.access_token,
            "Content-Type": "application/json;charset=UTF-8"
        }
        params = {"payNo": self.payorderno}
        with self.client.get(url=url, headers=headers, params=params, name="/mobile/payment/queryWalletPayOrder",
                             catch_response=True) as r:
            if r.json()["code"] == 200:
                r.success()
            else:
                r.failure("status_code != 200")


class WebsiteUser(HttpUser):
    host = "http://uc2-uat.perfect99.com"
    tasks = [SearchPay]

    # 创建先进先出队列实例
    user_data_queue = queue.Queue()

    # 获取项目根目录
    base_path = base_path()

    # 加载测试数据参数
    with io.open(base_path + "/data/user_pwd.csv", "r", encoding='utf-8') as csvfile:
        reader = csv.DictReader(csvfile)
        for row_dict in reader:
            user_data_queue.put_nowait(row_dict)

    min_wait = 2000
    max_wait = 3000

