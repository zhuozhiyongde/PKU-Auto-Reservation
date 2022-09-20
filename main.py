from datetime import datetime
from session import Session
import os


assert all(key in os.environ for key in [
           'STUDENTID', 'PASSWORD', 'DESCRIPTION', 'PLACES', 'DELTA']), "Not all keys are provided"

username = os.environ['STUDENTID']
password = os.environ['PASSWORD']
places = os.environ['PLACES'].split(',')
description = os.environ['DESCRIPTION']
delta = int(os.environ['DELTA'])

if __name__ == '__main__':
    print(datetime.now())
    s = Session()
    s.login(username, password)

    if s.request_passed(delta):
        exit(0)

    try:
        s.save_request(places, description, delta)

    except Exception as e:
        msg = e.args[0]['msg'] if 'msg' in e.args[0] else e.args[0]
        if '存在尚未审核通过的园区往返申请记录' in msg:
            s.get_latest()['sqbh']
        else:
            print(msg)
            exit(1)

    s.submit()
    print('已申请')
