from session import Session
import os


assert 'STUDENTID' in os.environ, "请设置 STUDENTID"
assert 'PASSWORD' in os.environ, "请设置 PASSWORD"
assert 'DESCRIPTION' in os.environ, "请设置 DESCRIPTION"
assert 'PLACES' in os.environ, "请设置 PLACES"

username = os.environ['STUDENTID']
password = os.environ['PASSWORD']
places = os.environ['PLACES'].split(',')
description = os.environ['DESCRIPTION']
time = int(os.environ['DELTA'])

if __name__ == '__main__':
    s = Session()
    s.login(username, password)
    try:
        rowid = s.save(crxjtsx=description, yqc=places, yqr=places)
    except Exception as e:
        msg = e.args[0]['msg'] if 'msg' in e.args[0] else e.args[0]
        if '存在尚未审核通过的园区往返申请记录' in msg:
            rowid = s.get_latest()['sqbh']
        else:
            print(msg)
            exit(1)
    s.submit(rowid)
    exit(0)
