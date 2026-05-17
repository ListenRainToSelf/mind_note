# Mind Note — AI 笔记系统

一个面向未来的 **Markdown 笔记 AI 系统**，采用**服务端+客户端一体**架构，支持**云同步**，以**网页端**为主，致力于打造**人与 AI 协同办公、共同学习**的智能笔记体验。

---

## 功能特性

### 已实现

- **文件服务器抽象层** — 基于本地文件系统的 CRUD 封装，支持路径树结构，面向 Markdown 笔记的语义化操作（创建、读写、改名、移动、删除）
- **用户认证系统** — 基于文件系统的登录/注册/注销，无需外部数据库，支持网络模式与本地模式
- **双模式架构** — 网络模式（多用户）与本地模式（单用户）共用同一后端引擎
- **配置驱动** — 通过 `config.json` 控制运行模式和数据目录

### 规划中

- [ ] Web 前端界面（React / Vue）
- [ ] AI 助手集成（笔记摘要、问答、内容生成）
- [ ] 实时云同步（多端协作）
- [ ] 富文本编辑器（Markdown 所见即所得）
- [ ] 标签与全文搜索
- [ ] 笔记分类与知识图谱

---

## 项目架构

```
mind_note/
├── main.py                  # 应用入口（待开发）
├── config.json              # 全局配置文件
│
├── file_server/             # 后端服务层
│   ├── file_server.py       # 文件系统抽象层（底层文件操作 → 中层笔记语义 → 顶层初始化）
│   └── API.py               # API 接口层（local_API / network_API + Flask + 初始化）
│
├── com/                     # 前端客户端（待开发）
│   ├── config.json          # 前端配置
│   ├── templates/
│   │   └── index.html       # 主页模板
│   └── static/
│       ├── css/style.css    # 样式文件
│       └── js/script.js     # 前端逻辑
│
├── DATA/                    # 默认数据目录
│   ├── .mind_note/          # 本地模式数据文件
│   │   └── file_tree.json   # 路径树快照
│   └── .users/              # 网络模式用户数据
│       └── users.json       # 用户列表
│
└── README.md                # 本文件
```

### 架构分层

`file_server.py` 采用**三层抽象**设计：

| 层级         | 说明                                                                                           |
| ------------ | ---------------------------------------------------------------------------------------------- |
| **底层函数** | 直接与 `os` 模块交互，提供路径判断、遍历、创建、读写、删除等基础操作                           |
| **中层函数** | 面向"笔记"概念的语义化操作（`create_note`、`write_note`、`read_note` 等），自动补全 `.md` 后缀 |
| **顶层函数** | `init()` 初始化入口，根据 JSON 结构批量创建目录和文件                                          |

`API.py` 在此基础上封装了两套 API：

| API             | 说明                                          |
| --------------- | --------------------------------------------- |
| **local_API**   | 本地 API 占位（预留扩展）                     |
| **network_API** | 用户认证 API（登录/注册/注销） + 笔记管理 API |

---

## 快速开始

### 环境要求

- Python 3.13+
- Windows / Linux / macOS

### 安装与运行

```bash
# 1. 进入项目目录
cd mind_note

# 2. 激活虚拟环境
call .venv\Scripts\activate      # Windows
source .venv/bin/activate         # Linux / macOS

# 3. 启动应用
python main.py
```

### 配置说明

编辑 `config.json`：

```json
{
    "network_serve": true,
    "file_server_config": {
        "dir": "DATA",
        "port": 5000,
        "file_tree": {
            "local_init_path": {
                ".mind_note": ["file_tree.json", {"change_log": []}]
            },
            "network_init_path": {
                ".users": ["users.json"]
            }
        }
    }
}
```

| 配置项                    | 说明                                                |
| ------------------------- | --------------------------------------------------- |
| `network_serve`           | `true` 启用网络模式（多用户），`false` 启用本地模式 |
| `file_server_config.dir`  | 数据存储根目录，支持相对路径和绝对路径              |
| `file_tree.*_init_path`   | 初始目录结构定义，首次启动时自动创建                |
| `file_server_config.port` | Flask 服务端口                                      |

---

## 开发指南

### 运行测试

```bash
# 文件服务器模块测试（涵盖 32 项功能测试）
python file_server/file_server.py

# API 模块测试（涵盖 10 项用户认证测试）
python file_server/API.py
```

### 技术栈

| 组件     | 技术                              |
| -------- | --------------------------------- |
| 后端     | Python 3.13, Flask                |
| 文件系统 | os / json（零外部依赖）           |
| 前端     | HTML / CSS / JavaScript（规划中） |
| AI       | 待定（规划中）                    |
| 同步     | 待定（规划中）                    |

---

## 路线图

参见 [TODO.md](TODO.md)。

---

## License

MIT
