"""
API 模块 (API Module)

==== 概述 ====
本模块建立在 file_server 模块之上，提供两层 API 抽象：

  1. local_API —— 本地 API（预留扩展，暂未实现）
  2. network_API —— 网络 API，基于用户系统提供登录/注册/注销功能，
     管理 .users 目录下的用户数据

此外，模块还包含 init() 初始化函数，负责读取 config.json 配置，
根据 network_serve 标志选择网络或本地模式，并完成 file_server 的初始化。

==== 架构分层 ====
模块结构如下：

  全局变量
    ├── DIR (str): 数据根目录（从配置读取）
    └── app (Flask): Flask 应用实例（预留）

  network_API 类 —— 用户认证 API
    ├── login():   用户登录；若用户不存在则自动注册
    ├── register(): 用户注册（实际委托给 login）
    └── logout():  用户注销（删除用户目录和用户记录）

  local_API 类 —— 本地 API 占位（待扩展）
    └── pass

  init() 函数 —— 模块初始化入口
    └── 读取配置 → 设置 DIR → 初始化 file_server → 创建系统文件

==== 用户系统设计 ====
  - 用户数据存储在 DIR/.users/ 目录下
  - 用户列表文件：DIR/.users/users.json（JSON 数组）
    格式：[{"username": "alice", "password": "123"}, ...]
  - 每个用户在 DIR/.users/<用户名>/ 下有自己的目录，用于存放个人数据
  - 登录时若用户不存在，则自动创建账号（等价于注册）

==== 本地 vs 网络模式 ====
  - 网络模式 (network_serve=true)：
      使用 network_init_path 初始化目录结构
      创建 .users/ 目录和 users.json
  - 本地模式 (network_serve=false)：
      使用 local_init_path 初始化目录结构
      创建 .mind_note/ 目录和 file_tree.json
"""

import file_server
import json
import os
from flask import Flask, request, jsonify

# ============================================================
# 全局变量 —— 模块的核心状态
# ============================================================

# DIR (str): 数据根目录，从 config.json 的 file_server_config.dir 读取。
# 所有用户数据、笔记文件都将存放在此目录下。
DIR = ''

# app (Flask): Flask Web 应用实例，为后续提供 HTTP API 端点做准备。
# 当前仅作声明，路由绑定待后续扩展。
app = Flask(__name__)


# ============================================================
# network_API 类 —— 用户认证与账户管理 API
#
# 提供基于文件系统的用户认证机制，所有用户数据持久化存储在
# DIR/.users/ 目录下。无需外部数据库，完全依赖 JSON 文件。
#
# 认证流程：
#   1. 检查 users.json 中是否存在该用户名
#   2. 若存在，验证密码是否匹配
#   3. 若不存在，自动创建新用户（注册即登录）
#   4. 确保每个用户在 .users/ 下有自己的数据目录
# ============================================================
class network_API:
    #login
    @staticmethod
    def login(username, password):
        """
        用户登录（若用户不存在则自动注册）。

        实现逻辑：
          1. 检查用户是否已存在于 users.json
          2. 如果存在 -> 验证密码，匹配则返回 '登录成功'，否则返回 '用户名或密码错误或已被占用'
          3. 如果不存在 -> 将新用户追加到 users.json 并创建用户目录，返回 '注册成功'
          4. 整个过程中不生成 session/token，属于基础认证

        Args:
            username (str): 用户名
            password (str): 明文密码

        Returns:
            str: 操作结果描述
                 - '登录成功'：用户存在且密码正确
                 - '用户名或密码错误或已被占用'：用户存在但密码不匹配
                 - '注册成功'：用户不存在，已自动创建账号

        Side Effects:
            - 如为新用户，会追加记录到 users.json 文件
            - 如用户目录不存在，会自动创建 DIR/.users/<username>/
        """
        # 构建用户数据目录和用户列表文件的路径
        users_dir: str = os.path.join(DIR, '.users')
        users_list: list = json.loads(
            file_server.read_file(os.path.join(users_dir, 'users.json'))
        )
        users_name_list: list = [i['username'] for i in users_list]
        user_dir: str = os.path.join(users_dir, username)
        is_user_have: bool = username in users_name_list

        # 确保用户个人数据目录存在
        if not os.path.exists(user_dir):
            os.makedirs(user_dir, exist_ok=True)

        if is_user_have:
            # 用户已存在：验证密码
            if users_list[users_name_list.index(username)]['password'] == password:
                return {'state':True,'msg':'登录成功'}
            else:
                return {'state':False,'msg':'用户名或密码错误或已被占用'}
        else:
            # 用户不存在：自动注册（追加到用户列表并持久化）
            users_list.append({'username': username, 'password': password})
            file_server.write_file(
                os.path.join(users_dir, 'users.json'),
                json.dumps(users_list, ensure_ascii=False, indent=4)
            )

            return {'state':True,'msg':'注册成功'}
    #register
    @staticmethod
    def register(username, password):
        """
        用户注册（实际委托给 login 实现）。

        由于 login() 在检测到新用户时会自动完成注册流程，
        因此 register 直接复用 login 的逻辑。

        Args:
            username (str): 用户名
            password (str): 明文密码

        Returns:
            str: 操作结果描述
                 - '注册成功'：新用户创建完成
                 - '用户名或密码错误或已被占用'：该用户名已被他人注册
        """
        return network_API.login(username, password)
    #logout
    @staticmethod
    def logout(username, password):
        """
        用户注销（删除用户目录及其在 users.json 中的记录）。

        注销操作会：
          1. 验证用户名和密码是否匹配
          2. 从 users.json 中移除该用户记录
          3. 删除该用户在 .users/ 下的个人数据目录
          4. 将更新后的用户列表写回磁盘

        Args:
            username (str): 用户名
            password (str): 明文密码

        Returns:
            str: 操作结果描述
                 - '注销成功'：用户存在且密码正确，已删除账户
                 - '用户名或密码错误'：用户存在但密码不匹配
                 - '用户不存在'：该用户名未注册

        Side Effects:
            - 删除 DIR/.users/<username>/ 目录及其全部内容
            - 更新 DIR/.users/users.json 文件
        """
        # 构建用户数据目录和用户列表文件的路径
        users_dir: str = os.path.join(DIR, '.users')
        users_list: list = json.loads(
            file_server.read_file(os.path.join(users_dir, 'users.json'))
        )
        users_name_list: list = [i['username'] for i in users_list]
        user_dir: str = os.path.join(users_dir, username)
        is_user_have: bool = username in users_name_list

        if is_user_have:
            # 用户存在：验证密码后执行删除操作
            if users_list[users_name_list.index(username)]['password'] == password:
                # 删除用户个人数据目录
                file_server.delete_dir(user_dir)
                # 从内存列表中移除该用户
                users_list.pop(users_name_list.index(username))
                # 将更新后的列表写回磁盘
                file_server.write_file(
                    os.path.join(users_dir, 'users.json'),
                    json.dumps(users_list, ensure_ascii=False, indent=4)
                )
                return {'state':True,'msg':'注销成功'}
            else:
                return {'state':False,'msg':'用户名或密码错误'}
        else:
            # 用户不存在
            return {'state':False,'msg':'用户不存在'}
    #create_note
    @staticmethod
    def create_note(username,password,note_name):
        if not note_name:
            return {'state':False,'msg':'笔记名称不能为空'}
        if network_API.login(username,password)['state']:
            # 创建笔记目录
            note_dir: str = os.path.join(DIR,username,note_name)
            file_server.create_dir(note_dir)
            return {'state':True,'msg':'笔记创建成功'}
        else:
            return {'state':False,'msg':'笔记创建失败'}
    #delete_note
    @staticmethod
    def delete_note(username,password,note_name):
        if not note_name:
            return {'state':False,'msg':'笔记名称不能为空'}
        if network_API.login(username,password)['state']:
            # 删除笔记目录
            note_dir: str = os.path.join(DIR,username,note_name)
            file_server.delete_dir(note_dir)
            return {'state':True,'msg':'笔记删除成功'}
        else:
            return {'state':False,'msg':'笔记删除失败'}
    #write_note
    @staticmethod
    def write_note(username,password,note_name,content):
        if not note_name:
            return {'state':False,'msg':'笔记名称不能为空'}
        if not content:
            return {'state':False,'msg':'笔记内容不能为空'}
        if network_API.login(username,password)['state']:
            # 写入笔记内容
            note_dir: str = os.path.join(DIR,username,note_name)
            file_server.write_file(os.path.join(note_dir,'note.md'),content)
            return {'state':True,'msg':'笔记写入成功'}
        else:
            return {'state':False,'msg':'笔记写入失败'}
    #read_note
    @staticmethod
    def read_note(username,password,note_name):
        if not note_name:
            return {'state':False,'msg':'笔记名称不能为空'}
        if network_API.login(username,password)['state']:
            # 读取笔记内容
            note_dir: str = os.path.join(DIR,username,note_name)
            content: str = file_server.read_file(os.path.join(note_dir,'note.md'))
            return {'state':True,'msg':content}
        else:
            return {'state':False,'msg':'笔记读取失败'}
    #create_dir
    @staticmethod
    def create_dir(username,password,dir_path):
        if not network_API.login(username,password)['state']:
            return {'state':False,'msg':'登录失败'}
        if not os.path.exists(dir_path):
            os.makedirs(dir_path)
            return {'state':True,'msg':'目录创建成功'}
        else:
            return {'state':False,'msg':'目录已存在'}
    #delete_dir
    @staticmethod
    def delete_dir(username,password,dir_path):
        if not network_API.login(username,password)['state']:
            return {'state':False,'msg':'登录失败'}
        if os.path.exists(dir_path):
            try:
                os.rmdir(dir_path)
                return {'state':True,'msg':'目录删除成功'}
            except Exception as e:
                return {'state':False,'msg':f'目录删除失败：{e}'}
        else:
            return {'state':False,'msg':'目录不存在'}


# ============================================================
# local_API 类 —— 本地功能 API 占位
#
# 预留用于后续扩展本地模式的 API 接口。
# 当前为空实现，等待具体需求时补充。
# ============================================================
class local_API:
    #staticmethod
    @staticmethod
    def create_note(note_name):
        if not note_name:
            return {'state':False,'msg':'笔记名称不能为空'}
        if not os.path.exists(os.path.join(DIR,note_name)):
            os.makedirs(os.path.join(DIR,note_name))
            return {'state':True,'msg':'笔记创建成功'}
        elif os.path.exists(os.path.join(DIR,note_name)):
            return {'state':False,'msg':'笔记已存在'}
        else:
            return {'state':False,'msg':'笔记创建失败'}
    #delete_note
    @staticmethod
    def delete_note(note_name):
        if not note_name:
            return {'state':False,'msg':'笔记名称不能为空'}
        if os.path.exists(os.path.join(DIR,note_name)):
            try:
                os.rmdir(os.path.join(DIR,note_name))
                return {'state':True,'msg':'笔记删除成功'}
            except Exception as e:
                return {'state':False,'msg':f'笔记删除失败：{e}'}
        else:
            return {'state':False,'msg':'笔记不存在'}
    #write_note
    @staticmethod
    def write_note(note_name,content):
        if not note_name:
            return {'state':False,'msg':'笔记名称不能为空'}
        if not content:
            return {'state':False,'msg':'笔记内容不能为空'}
        if os.path.exists(os.path.join(DIR,note_name)):
            file_server.write_file(os.path.join(DIR,note_name,'note.md'),content)
            return {'state':True,'msg':'笔记写入成功'}
        else:
            return {'state':False,'msg':'笔记不存在'}
    #read_note
    @staticmethod
    def read_note(note_name):
        if not note_name:
            return {'state':False,'msg':'笔记名称不能为空'}
        if os.path.exists(os.path.join(DIR,note_name)):
            content: str = file_server.read_file(os.path.join(DIR,note_name,'note.md'))
            return {'state':True,'msg':content}
        else:
            return {'state':False,'msg':'笔记不存在'}
    #create_dir
    @staticmethod
    def create_dir(dir_path):
        if not dir_path:
            return {'state':False,'msg':'目录路径不能为空'}
        if not os.path.exists(dir_path):
            os.makedirs(dir_path)
            return {'state':True,'msg':'目录创建成功'}
        elif os.path.exists(dir_path):
            return {'state':False,'msg':'目录已存在'}
        else:
            return {'state':False,'msg':'目录创建失败'}
    #delete_dir
    @staticmethod
    def delete_dir(dir_path):
        if not dir_path:
            return {'state':False,'msg':'目录路径不能为空'}
        if os.path.exists(dir_path):
            try:
                os.rmdir(dir_path)
                return {'state':True,'msg':'目录删除成功'}
            except Exception as e:
                return {'state':False,'msg':f'目录删除失败：{e}'}
        else:
            return {'state':False,'msg':'目录不存在'}


# ============================================================
# 初始化函数 —— 读取配置，启动文件服务器
# ============================================================
def init():
    """
    从 config.json 读取配置，初始化文件服务器并创建系统文件。

    初始化流程：
      1. 读取 config.json 的 file_server_config 和 network_serve 字段
      2. 设置全局 DIR 并同步到 file_server 模块
      3. 根据 network_serve 标志选择初始化模式：
         - 网络模式：创建 .users/ 目录和 users.json（空数组）
         - 本地模式：创建 .mind_note/ 目录和 file_tree.json（路径树快照）
      4. 执行 file_server.init() 创建工作目录和初始文件结构

    config.json 结构参考：
        {
            "file_server_config": {
                "dir": "C:/data",
                "file_tree": {
                    "network_init_path": { ... },
                    "local_init_path": { ... }
                }
            },
            "network_serve": true
        }

    Side Effects:
        - 修改全局变量 DIR
        - 调用 file_server.set_DIR() 同步工作目录
        - 在 DIR 下创建 .users/ 或 .mind_note/ 等系统目录
    """
    # 读取配置文件
    with open('config.json', 'r', encoding='utf-8') as f:
        config = json.load(f)

    file_server_config = config['file_server_config']
    network_serve = config['network_serve']
    if config['file_server_config']['dir'] == '':
        return {'state':False,'msg':'目录不能为空不能为空'}
    else:
        global DIR
        if file_server.is_abs_windows(file_server_config['dir']):
            DIR = file_server_config['dir']
        else:
            DIR = os.path.join(os.getcwd(), file_server_config['dir'])

    file_server.set_DIR(DIR)

    print('数据初始化完成')
    print(f'数据库地址：{DIR}')

    if network_serve:
        # 网络模式：初始化目录结构 + 创建用户系统文件
        file_server.init(file_server_config['file_tree']['network_init_path'])
        if file_server.read_file(os.path.join(DIR, '.users', 'users.json')) == '':
            file_server.write_file(
                os.path.join(DIR, '.users', 'users.json'),
                json.dumps([], ensure_ascii=False, indent=4)
            )
    else:
        # 本地模式：初始化目录结构 + 创建路径树快照文件
        file_server.init(file_server_config['file_tree']['local_init_path'])
        if file_server.read_file(os.path.join(DIR, '.mind_note', 'file_tree.json')) == '':
            file_server.write_file(
                os.path.join(DIR, '.mind_note', 'file_tree.json'),
                json.dumps(file_server.get_path_tree(), ensure_ascii=False, indent=4)
            )


# ============================================================
# 调试入口 —— 直接运行此模块时执行的功能测试
#
# 覆盖以下测试场景：
#   1. 初始化文件服务器和用户系统
#   2. 新用户注册（自动注册：登录一个不存在的用户）
#   3. 已存在用户的正确密码登录
#   4. 已存在用户的错误密码登录
#   5. 注册已存在用户（密码正确 / 密码错误）
#   6. 错误密码注销
#   7. 正确密码注销
#   8. 注销不存在的用户
#   9. 重新注册已注销用户（验证用户数据已彻底清除）
#   10. 清理：删除测试用户目录
#
# 预期输出格式：每个测试用例输出 [测试名] → {结果}
# ============================================================
if __name__ == '__main__':
    # 用于测试的用户凭据
    TEST_USER = 'test_user'
    TEST_PASS = 'pass123'
    WRONG_PASS = 'wrong_pass'

    # 步骤 0：初始化文件服务器与用户系统
    # --------------------------------------------------
    print('=' * 60)
    print('【初始化】')
    print('=' * 60)
    init()
    local_API()
    print('初始化完成，开始功能测试...\n')

    # 步骤 1：新用户注册（自动注册）
    # --------------------------------------------------
    print('-' * 60)
    result = network_API.login(TEST_USER, TEST_PASS)
    print(f'【测试 1】新用户注册 (login 新用户) → {result}')
    # state=True, msg='注册成功'
    assert result['state'] is True, '新用户注册失败！'
    assert '注册成功' in result['msg'], f'期望"注册成功"，实际"{result["msg"]}"'
    print('  ✓ 测试通过\n')

    # 步骤 2：已存在用户的正确密码登录
    # --------------------------------------------------
    print('-' * 60)
    result = network_API.login(TEST_USER, TEST_PASS)
    print(f'【测试 2】正确密码登录 → {result}')
    # state=True, msg='登录成功'
    assert result['state'] is True, '正确密码登录失败！'
    assert '登录成功' in result['msg'], f'期望"登录成功"，实际"{result["msg"]}"'
    print('  ✓ 测试通过\n')

    # 步骤 3：已存在用户的错误密码登录
    # --------------------------------------------------
    print('-' * 60)
    result = network_API.login(TEST_USER, WRONG_PASS)
    print(f'【测试 3】错误密码登录 → {result}')
    # state=False, msg='用户名或密码错误或已被占用'
    assert result['state'] is False, '错误密码应当登录失败！'
    assert '错误' in result['msg'], f'期望包含"错误"，实际"{result["msg"]}"'
    print('  ✓ 测试通过\n')

    # 步骤 4：注册已存在用户（密码正确 → 等价于登录）
    # --------------------------------------------------
    print('-' * 60)
    result = network_API.register(TEST_USER, TEST_PASS)
    print(f'【测试 4】注册已存在用户 (密码正确) → {result}')
    # register 委托给 login，密码匹配 -> state=True, msg='登录成功'
    assert result['state'] is True, '已存在用户注册(密码正确)应当返回登录成功！'
    assert '登录成功' in result['msg'], f'期望"登录成功"，实际"{result["msg"]}"'
    print('  ✓ 测试通过\n')

    # 步骤 5：注册已存在用户（密码错误）
    # --------------------------------------------------
    print('-' * 60)
    result = network_API.register(TEST_USER, WRONG_PASS)
    print(f'【测试 5】注册已存在用户 (密码错误) → {result}')
    # register 委托给 login，密码不匹配 -> state=False
    assert result['state'] is False, '已存在用户注册(密码错误)应当失败！'
    assert '错误' in result['msg'], f'期望包含"错误"，实际"{result["msg"]}"'
    print('  ✓ 测试通过\n')

    # 步骤 6：错误密码注销
    # --------------------------------------------------
    print('-' * 60)
    result = network_API.logout(TEST_USER, WRONG_PASS)
    print(f'【测试 6】错误密码注销 → {result}')
    # state=False, msg='用户名或密码错误'
    assert result['state'] is False, '错误密码注销应当失败！'
    assert '错误' in result['msg'], f'期望包含"错误"，实际"{result["msg"]}"'
    print('  ✓ 测试通过\n')

    # 步骤 7：正确密码注销
    # --------------------------------------------------
    print('-' * 60)
    result = network_API.logout(TEST_USER, TEST_PASS)
    print(f'【测试 7】正确密码注销 → {result}')
    # state=True, msg='注销成功'
    assert result['state'] is True, '正确注销应当成功！'
    assert '注销成功' in result['msg'], f'期望"注销成功"，实际"{result["msg"]}"'
    print('  ✓ 测试通过\n')

    # 步骤 8：注销不存在的用户（验证用户已从系统中移除）
    # --------------------------------------------------
    print('-' * 60)
    result = network_API.logout(TEST_USER, TEST_PASS)
    print(f'【测试 8】注销不存在的用户 → {result}')
    # 用户已被删除 -> state=False, msg='用户不存在'
    assert result['state'] is False, '不存在的用户注销应当失败！'
    assert '不存在' in result['msg'], f'期望包含"不存在"，实际"{result["msg"]}"'
    print('  ✓ 测试通过\n')

    # 步骤 9：重新注册已注销用户（验证用户数据已彻底清除）
    # --------------------------------------------------
    print('-' * 60)
    result = network_API.login(TEST_USER, TEST_PASS)
    print(f'【测试 9】重新注册已注销用户 → {result}')
    # 用户已被彻底删除 -> 视为新用户注册
    assert result['state'] is True, '重新注册应当成功！'
    assert '注册成功' in result['msg'], f'期望"注册成功"，实际"{result["msg"]}"'
    print('  ✓ 测试通过\n')

    # 步骤 10：清理测试用户
    # --------------------------------------------------
    print('-' * 60)
    print('【清理】删除测试用户...')
    network_API.logout(TEST_USER, TEST_PASS)
    print(f'用户 "{TEST_USER}" 已清理\n')

    # 汇总
    # --------------------------------------------------
    print('=' * 60)
    print('所有测试已通过 ✓')
    print('=' * 60)
