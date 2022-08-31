from datetime import datetime, timedelta
import json
import requests
import random
from urllib import parse
from functools import wraps

# test
saveInput = {
    "crxjtsx": "吃饭开会见女友",
    "crxrq": "20220901",
    "yqc": [
        "燕园",
        "万柳园区"
    ],
    "yqr": [
        "燕园",
        "万柳园区"
    ],
}


class Session(requests.Session):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/80.0.3987.149 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9',
            'Accept-Language': 'zh-CN,zh;q=0.9',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Cache-Control': 'max-age=0',
            'TE': 'Trailers',
            'Pragma': 'no-cache',
            'Connection': 'keep-alive',
        })

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

    def login(self, username: str, password: str) -> bool:
        """登录门户，重定向出入校申请"""
        # IAAA 登录
        json = self.post("https://iaaa.pku.edu.cn/iaaa/oauthlogin.do", data={
            "userName": username,
            "appid": "portal2017",
            "password": password,
            "redirUrl": "https://portal.pku.edu.cn/portal2017/ssoLogin.do",
            "randCode": "",
            "smsCode": "",
            "optCode": "",
        }).json()
        assert json['success'], json

        # 门户 token 验证
        self.get('https://portal.pku.edu.cn/portal2017/ssoLogin.do', params={
            '_rand': random.random(),
            'token': json['token']
        })

        # 学生出入校重定向
        res = self.get(
            'https://portal.pku.edu.cn/portal2017/util/appSysRedir.do?appId=stuCampusExEn')
        redir = parse.parse_qs(parse.urlparse(res.url).query)
        token = redir['token'][0]

        # 登录学生出入校
        json = self.get('https://simso.pku.edu.cn/ssapi/simsoLogin', params={
            'token': token
        }).json()
        assert json['success']
        sid = json['sid']

        # 设置请求参数
        self.params['sid'] = sid
        self.params['_sk'] = username
        self.cookies.set('sid', sid, domain='simso.pku.edu.cn')

        # 获取出入校申请时段信息
        return self.login_check()

    def login_check(self):
        json = self.get(
            'https://simso.pku.edu.cn/ssapi/stuaffair/epiApply/getJrsqxx').json()
        return json['success'] and json['row']['sfyxsq'] == 'y'

    @wraps('check_login')
    def login_check_wrapper(func):
        def wrapper(self, *args, **kwargs):
            if not self.login_check():
                raise Exception('You should login first to use this method')
            return func(self, *args, **kwargs)
        return wrapper

    @login_check_wrapper
    def status(self):
        # 获取申请状态
        json = self.get(
            'https://simso.pku.edu.cn/ssapi/stuaffair/epiApply/getSqzt').json()
        assert json['success']
        return json

    def get_supplement(self):
        lxxx = self.status()['row']['lxxx']
        lxxx.update(dzyx=lxxx['email'], lxdh=lxxx['yddh'])
        assert all(k in lxxx for k in [
                   'yddh', 'ssfjh', 'ssl', 'ssyq', 'dzyx', 'lxdh']), '无法获取住宿、联系信息'
        return lxxx

    def save(self, delta=0, **info):
        """尝试保存出入校信息"""
        # supplement info
        template = {
            "crxrq": (datetime.now() + timedelta(days=delta)).strftime('%Y%m%d'),
            "sqbh": "",
            "crxqd": "",
            "crxzd": "",
            "qdbc": "",
            "zdbc": "",
            "qdxm": "",
            "zdxm": "",
            "crxsy": "园区往返",
            "gjdqm": "156",
            "ssdm": "",
            "djsm": "",
            "xjsm": "",
            "jd": "",
            "bcsm": "",
            "crxxdgj": "",
            "dfx14qrbz": "y",
            "sfyxtycj": "",
            "tjbz": "",
            "shbz": "",
            "shyj": "",
            "fxjwljs": "",
            "fxzgfxljs": "",
            "fxqzmj": "",
            "fxyczz": "",
        }
        template.update(**self.get_supplement())
        template.update(info)

        assert all(k in template for k in [
                   'crxjtsx', 'yqc', 'yqr']), '出入校信息不完整'

        json = self.post('https://simso.pku.edu.cn/ssapi/stuaffair/epiApply/saveSqxx',
                         params={'applyType': 'yqwf'}, json=template).json()
        assert json['success'], json
        return json['row']

    def submit(self, row) -> bool:
        # 提交申请信息
        json = self.get('https://simso.pku.edu.cn/ssapi/stuaffair/epiApply/submitSqxx', params={
            'sqbh': row
        }).json()
        return json['success']

    def get_latest(self):
        # 获取最近的申请信息
        json = self.get(
            'https://simso.pku.edu.cn/ssapi/stuaffair/epiApply/getSqxxHis?pageNum=1').json()
        assert json['success']
        return json['row'][0]


def prettify(data):
    return json.dumps(data, indent=2, ensure_ascii=False, sort_keys=True)
