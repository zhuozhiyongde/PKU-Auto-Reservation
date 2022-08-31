# 园区往返自动报备

[完整教程](https://xiaotianxt.com/posts/informal/pku-simso-free/) （并没有开始写）

## 使用说明

1. Fork 本仓库。
2. 激活 github actions。
3. 设置如下 Repository Secrets：

    - `STUDENTID`: 校园卡号，如：`2201114514`。
    - `PASSWORD`: 门户登录密码，如：`abc123`。
    - `DELTA`: `0` 申请当天，`1` 申请第二天，以此类推。
    - `DESCRIPTION`: 出入校具体事项（原因），如：`吃饭睡觉见女友`。
    - `PLACES`: 出入园区列表，使用**英文逗号隔开**，如：`燕园,万柳园区`。
