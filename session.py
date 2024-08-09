#!/usr/bin/env python
# -*- encoding: utf-8 -*-
# @Author  :   Arthals
# @File    :   session.py
# @Time    :   2024/08/10 03:06:47
# @Contact :   zhuozhiyongde@126.com
# @Software:   Visual Studio Code


import random
from functools import wraps
from urllib import parse

import requests


class Session(requests.Session):
    def __init__(self, config, notifier=None, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._config = config
        self._notifier = notifier
        self.headers.update(
            {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/80.0.3987.149 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9",
                "Accept-Language": "zh-CN,zh;q=0.9",
                "Accept-Encoding": "gzip, deflate",
                "Connection": "keep-alive",
                "Upgrade-Insecure-Requests": "1",
                "Cache-Control": "max-age=0",
                "TE": "Trailers",
                "Pragma": "no-cache",
            }
        )
        self._base_url = "https://simso.pku.edu.cn/ssapi/"

        assert self._config["mode"] in ["燕园", "新燕园"], "Invalid mode"
        if self._config["mode"] == "燕园":
            self._base_url += "stuaffair/epiVisitorAppt"
        elif self._config["mode"] == "新燕园":
            self._base_url += "bwb/cpVisitorAppt"

    def __del__(self):
        self.close()

    def get(self, url, *args, **kwargs):
        """重写 get 方法，验证状态码，转化为 json"""
        res = super().get(url, *args, **kwargs)
        res.raise_for_status()
        return res

    def post(self, url, *args, **kwargs):
        """重写 post 方法，验证状态码，转化为 json"""
        res = super().post(url, *args, **kwargs)
        res.raise_for_status()

        return res

    def login(self) -> bool:
        """登录门户，重定向出入校申请"""
        # IAAA 登录
        json = self.post(
            "https://iaaa.pku.edu.cn/iaaa/oauthlogin.do",
            data={
                "userName": self._config["username"],
                "appid": "portal2017",
                "password": self._config["password"],
                "redirUrl": "https://portal.pku.edu.cn/portal2017/ssoLogin.do",
                "randCode": "",
                "smsCode": "",
                "optCode": "",
            },
        ).json()
        assert json["success"], json

        # 门户 token 验证
        self.get(
            "https://portal.pku.edu.cn/portal2017/ssoLogin.do",
            params={"_rand": random.random(), "token": json["token"]},
        )

        # 学生出入校重定向
        res = self.get(
            "https://portal.pku.edu.cn/portal2017/util/appSysRedir.do?appId=simso-biz&p1=sadEpiVisitorAppt"
        )
        redir = parse.parse_qs(parse.urlparse(res.url).query)
        token = redir["token"][0]

        # 登录学生出入校
        json = self.get(
            "https://simso.pku.edu.cn/ssapi/simsoLogin", params={"token": token}
        ).json()
        assert json["success"], json
        sid = json["sid"]

        # 设置请求参数
        self.params["sid"] = sid
        self.params["_sk"] = self._config["username"]
        self.cookies.set("sid", sid, domain="simso.pku.edu.cn")

        # 获取出入校申请时段信息
        return self.login_check()

    def login_check(self):
        """检查是否已登录"""
        json = self.get(
            "https://simso.pku.edu.cn/ssapi/stuaffair/epiApply/getJrsqxx"
        ).json()
        return json["success"] and json["row"]["sfyxsq"] == "y"

    @wraps(login_check)
    def login_check_wrapper(func):
        def wrapper(self, *args, **kwargs):
            if not self.login_check():
                raise Exception("You should login first to use this method")
            return func(self, *args, **kwargs)

        return wrapper

    @login_check_wrapper
    def status(self):
        """获取申请状态（当前是否可申请）"""
        """
        GET:
        https://simso.pku.edu.cn/ssapi/stuaffair/epiVisitorAppt/checkSqrq?sid=ae14f8b3-7b29-4cd8-933e-ab92c3572f1d2110000000&_sk=2110000000&sqrq=20240101
        
        Return:
        {
            "code": 1,
            "row": null,
            "success": true,
            "msg": "成功",
            "timestamp": 1723230066512
        }
        """
        json = self.get(
            f"{self._base_url}/checkSqrq",
            params={
                "sid": self.params["sid"],
                "_sk": self.params["_sk"],
                "sqrq": self._config["yyrq"],
            },
        ).json()
        # print(json)
        assert json["success"], json["msg"]
        return json

    def save_request(self, appointment):
        # 检查是否可申请
        self.status()

        """尝试保存出入校信息"""
        """
        {
            "lxdh": "16666666666",
            "yyrq": "20240101",
            "yyxm": "东侧门",
            "yysy": "游览",
            "yysj": "10:00"
            "byyrxm": "张三",
            "byyrlxdh": "11111111111",
            "byyrzjh": "110101200001011111",
        }
        """
        template = {
            "lxdh": self._config["phone"],
            "yyrq": self._config["yyrq"],
            "yyxm": self._config["yyxm"],
            "yysj": self._config["yysj"],
            "yysy": self._config["yysy"],
        }
        template.update(appointment)

        """
        POST:
        https://simso.pku.edu.cn/ssapi/stuaffair/epiVisitorAppt/saveSqxx?sid=ae14f8b3-7b29-4cd8-933e-ab92c3572f1d2110000000&_sk=2110000000
        
        Return:
        {
            "code": 1,
            "row": "sqxx20240101000001",
            "success": true,
            "msg": "success",
            "timestamp": 1704038401000
        }
        """
        res = self.post(
            f"{self._base_url}/saveSqxx",
            params={"sid": self.params["sid"], "_sk": self.params["_sk"]},
            json=template,
        ).json()
        assert res["success"], res["msg"]

        return res["row"]

    def request_2fa_code(self, sqxxid):
        """
        GET:
        https://simso.pku.edu.cn/ssapi/stuaffair/epiVisitorAppt/sendEcyzCode?sid=ae14f8b3-7b29-4cd8-933e-ab92c3572f1d2110000000&_sk=2110000000&sqxxid=sqxx20240101000001

        Return:
        {
          "code": 1,
          "row": {
            "flag": true,
            "errmsg": "",
            "type": "opt"
          },
          "success": true,
          "msg": "操作成功！",
          "timestamp": 1704038401001
        }
        """
        res = self.get(
            f"{self._base_url}/sendEcyzCode",
            params={
                "sid": self.params["sid"],
                "_sk": self.params["_sk"],
                "sqxxid": sqxxid,
            },
        ).json()
        assert res["success"], res["msg"]
        return

    def submit_request(self, appointment) -> bool:
        sqxxid = self.save_request(appointment)
        self.request_2fa_code(sqxxid)
        code = input("Please input the 2FA code: ")
        """
        GET:
        https://simso.pku.edu.cn/ssapi/stuaffair/epiVisitorAppt/submitSqxx?sid=ae14f8b3-7b29-4cd8-933e-ab92c3572f1d2110000000&_sk=2110000000&sqxxid=sqxx20240101000001&code=123456
        
        Return:
        {
            "code": 1,
            "row": "sqxx20240101000001",
            "success": true,
            "msg": "success",
            "timestamp": 1704038401002
        }
        """
        res = self.get(
            f"{self._base_url}/submitSqxx",
            params={
                "sid": self.params["sid"],
                "_sk": self.params["_sk"],
                "sqxxid": sqxxid,
                "code": code,
            },
        ).json()
        assert res["success"], res["msg"]
        print(f"{'[Succeed]':<15}: {appointment['byyrxm']}")
        if self._notifier:
            self._notifier.send(f"Succeed: {appointment['byyrxm']}")
        return

    def submit_all(self):
        """提交所有申请"""

        for appointment in self._config["appointments"]:
            converted_data = {
                "byyrxm": appointment["name"],
                "byyrzjh": appointment["id"],
                "byyrlxdh": appointment["phone"],
            }
            self.submit_request(converted_data)


class BarkNotifier:
    def __init__(self, token):
        self._token = token

    def send(self, body):
        requests.post(
            f"https://api.day.app/{self._token}",
            data={
                "title": "PKU-Auto-Reservation",
                "body": body,
                "icon": "https://cdn.arthals.ink/pku.jpg",
                "level": "timeSensitive",
            },
        )
