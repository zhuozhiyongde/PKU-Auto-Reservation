#!/usr/bin/env python
# -*- encoding: utf-8 -*-
# @Author  :   Arthals
# @File    :   server-example.py
# @Time    :   2024/08/10 05:55:05
# @Contact :   zhuozhiyongde@126.com
# @Software:   Visual Studio Code


from fastapi import FastAPI, Request, Response

app = FastAPI()


@app.post("/pku_sms")
async def sms(request: Request):
    headers = request.headers
    if headers.get("Authorization", None) != "123456":
        return Response(status_code=403)
    data = await request.json()
    with open("./code.txt", "w") as f:
        f.write(data["content"])
    print(data)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
