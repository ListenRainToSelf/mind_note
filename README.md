# 项目介绍

## 项目功能

注重于开发服务端客户端一体、拥有云同步、以网页为主的，md格式笔记AI系统，注重于开发AI与人共同办公、共同学习，可以帮助用户更好的学习和工作。

## 项目架构

目录结构如下：

```path
/- mind_note
    /- .venv  # 虚拟环境
    /- com  #客户端网页文件
    /- DATA  # 默认数据文件
        /- .mind_note  # 私人 mind_note 数据文件
        /- .user  # 服务端用户数据文件
    /- file_server  # 文件管理
        /- API.py  # API 接口文件
        /- file_server.py  # 文件管理文件
    /- config.json  # 配置文件
```

## 食用方法

使用cmd进入项目_note目录，执行以下命令：

```bath
call .venv\Scripts\activate
python main.py
```
