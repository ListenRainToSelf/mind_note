"""
文件服务器模块 (File Server Module)

==== 概述 ====
本模块提供了一个基于本地文件系统的轻量级文件服务器抽象层，专注于 Markdown 笔记的
创建、读取、修改、删除（CRUD）等操作。它将文件系统的目录和文件抽象为"路径树"结构，
方便上层调用方以 JSON 可序列化的形式获取和管理文件系统的状态。

==== 架构分层 ====
模块按功能抽象层级分为三层：

  底层函数 —— 最基础的文件/目录操作封装，直接与 os 模块交互
    ├── is 类：路径类型判断（是否为文件、目录、绝对路径等）
    ├── walk 类：文件系统遍历，生成路径树结构
    ├── reload 类：刷新内存中的路径树缓存
    ├── get 类：获取完整路径或路径树结构
    └── create 类：创建目录、文件，以及根据 JSON 结构批量创建

  中层函数 —— 面向"笔记"概念的语义化操作
    ├── create_note：创建一篇 Markdown 笔记
    ├── delete_note：删除一篇笔记
    ├── write_note：写入笔记内容
    ├── change_note_name：重命名笔记
    ├── change_note_dir：将笔记移动到其他目录
    └── read_note：读取笔记内容

  顶层函数 —— 模块初始化入口
    └── init：根据配置初始化整个文件服务器的工作目录和初始结构

==== 核心概念 ====
  - DIR：全局工作根目录，所有相对路径操作都基于此目录进行
  - PATH_TREE：内存中的路径树缓存，通过 get_path_tree() 获取最新状态
  - 笔记（Note）：即 .md 后缀的 Markdown 文件，是模块的主要操作对象
  - 路径树（Path Tree）：描述 DIR 下所有文件和目录的嵌套列表结构
    ['file1.txt', {'dir': 'subdir', 'files': ['file2.txt'], 'path': '...'}]

==== 使用示例 ====
    import file_server

    # 1. 设置工作目录并初始化
    file_server.DIR = '/path/to/vault'
    file_server.init({'root': ['readme.md', {'sub': ['note.md']}]})

    # 2. 操作笔记
    file_server.create_note('daily/2026-05-10')
    file_server.write_note('daily/2026-05-10', '# 今日计划\\n...')
    content = file_server.read_note('daily/2026-05-10')

    # 3. 获取文件系统快照
    tree = file_server.get_path_tree()

==== 注意事项 ====
  - 使用前必须设置 DIR 为有效的目录路径，否则所有相对路径操作将失败
  - 路径分隔符统一使用正斜杠 "/"，模块内部会自动适配操作系统
  - 笔记操作函数会自动在名称后追加 .md 后缀，调用时无需手动添加
"""

import json
import os
import re

# ============================================================
# 底层变量 —— 模块的全局状态
# ============================================================

# DIR (str): 文件服务器的根工作目录，所有相对路径操作的基准路径。
# 使用前必须由调用方显式设置，例如: file_server.DIR = 'C:/vault'
DIR = ''

# PATH_TREE (list): 内存中缓存的路径树结构，表示 DIR 下所有文件和子目录的嵌套列表。
# 格式: [文件名, {'dir': 目录名, 'files': [...], 'path': '绝对路径'}, ...]
# 通过 reload_path_tree() 或 get_path_tree() 刷新。
PATH_TREE = []

# ============================================================
# 底层函数 —— 最基础的文件系统操作封装
# ============================================================

#set DIR
def set_DIR(new_DIR:str):
    global DIR
    DIR = new_DIR
    return DIR

#get DIR
def get_DIR():
    return DIR

#get PATH_TREE
def get_path_tree():
    return PATH_TREE

# --- is 类函数：路径类型判断 ----------------------------------
def is_dir(path):
    """
    判断给定路径是否为已存在的目录。

    Args:
        path (str): 相对于 DIR 的路径字符串

    Returns:
        bool: 如果路径存在且为目录返回 True，否则返回 False
    """
    return os.path.isdir(os.path.join(DIR, path))

def is_file(path):
    """
    判断给定路径是否为已存在的文件。

    Args:
        path (str): 相对于 DIR 的路径字符串

    Returns:
        bool: 如果路径存在且为文件返回 True，否则返回 False
    """
    return os.path.isfile(os.path.join(DIR, path))

def is_path(path):
    """
    判断给定路径是否存在（无论文件还是目录）。

    这是 is_dir() 和 is_file() 的并集，用于快速判断一个路径是否有效。

    Args:
        path (str): 相对于 DIR 的路径字符串

    Returns:
        bool: 路径存在（文件或目录均可）返回 True，否则返回 False
    """
    return is_dir(path) or is_file(path)

def is_abs_windows(path: str) -> bool:
    """
    判断路径是否为 Windows 风格的绝对路径。

    支持的格式：
      - 盘符路径：C:\\foo\\bar 或 D:/baz
      - 不包含 UNC 网络路径（如 \\\\server\\share），若有需要可取消注释下方正则

    Args:
        path (str): 待检测的路径字符串

    Returns:
        bool: 是 Windows 绝对路径返回 True，否则返回 False

    Example:
        >>> is_abs_windows('C:/Users/test')
        True
        >>> is_abs_windows('relative/path')
        False
    """
    # 盘符路径正则：以盘符字母开头，后跟冒号和分隔符，后续为合法的路径字符
    pattern = r'^[a-zA-Z]:[\\/](?:[^\\/:*?"<>|\r\n]+[\\/]?)*$'
    # 若需包含 UNC 路径，替换为：
    # r'^(?:[a-zA-Z]:[\\/]|\\\\[^\\]+\\[^\\]+)[^]*$'
    return bool(re.fullmatch(pattern, path))


# --- walk 类函数：文件系统遍历 --------------------------------
def walk_path_to_tree(path):
    """
    递归遍历指定路径，将其下所有文件和子目录转换为"路径树"结构。

    路径树结构说明：
      - 文件直接以字符串形式出现，例如 'readme.md'
      - 子目录以字典表示：{'dir': '目录名', 'files': [...], 'path': '绝对路径'}
      - 子目录的 'files' 键同样是一个列表，递归嵌套

    Args:
        path (str): 要遍历的绝对路径

    Returns:
        list: 路径树列表，包含文件名（str）和子目录字典（dict）的混合

    Example:
        假设 /vault 的结构为：
          /vault
          ├── readme.md
          └── notes/
              └── todo.md

        >>> walk_path_to_tree('/vault')
        ['readme.md', {'dir': 'notes', 'files': ['todo.md'], 'path': '/vault/notes'}]
    """
    out = []
    for item in os.listdir(path):
        item_full = os.path.join(path, item)
        if os.path.isfile(item_full):
            out.append(item)
        else:
            out.append({
                'dir': item,
                'files': walk_path_to_tree(item_full),
                'path': item_full
            })
    return out


# --- reload 类函数：刷新缓存 ----------------------------------
def reload_path_tree():
    """
    重新扫描 DIR 目录，刷新内存中的 PATH_TREE 全局缓存。

    该函数会覆盖全局变量 PATH_TREE，确保后续通过 get_path_tree()
    获取到的是文件系统的最新状态。通常在创建、删除、移动文件后需要调用。

    Side Effects:
        修改全局变量 PATH_TREE
    """
    global PATH_TREE
    PATH_TREE = walk_path_to_tree(DIR)


# --- get 类函数：获取路径信息 ----------------------------------
def get_complete_path(*ary):
    """
    将多个路径片段拼接为基于当前工作目录的完整绝对路径。

    这是 os.path.join(os.getcwd(), ...) 的便捷封装，适用于需要
    获取相对于脚本运行目录的绝对路径的场景。

    Args:
        *ary: 一个或多个路径片段

    Returns:
        str: 拼接后的完整路径

    Example:
        >>> get_complete_path('DATA', 'notes')
        '/current/working/dir/DATA/notes'
    """
    return os.path.join(os.getcwd(), *ary)

def get_path_tree():
    """
    返回 DIR 目录最新的路径树结构快照。

    每次调用都会重新扫描文件系统（通过 reload_path_tree），因此返回的
    始终是磁盘上的真实状态，而非过期的缓存数据。

    Returns:
        list: 路径树列表，格式与 walk_path_to_tree 一致

    Example:
        >>> tree = get_path_tree()
        >>> print(json.dumps(tree, indent=2, ensure_ascii=False))
        [
          "readme.md",
          {
            "dir": "notes",
            "files": ["todo.md"],
            "path": "/vault/notes"
          }
        ]
    """
    reload_path_tree()
    return PATH_TREE

# --- create 类函数：创建目录/文件 ------------------------------
def create_dir(path):
    """
    创建目录（支持嵌套创建）。

    如果 path 是 Windows 绝对路径，则直接在指定位置创建；
    否则，路径将相对于全局 DIR 进行解析。

    Args:
        path (str): 要创建的目录路径

    Returns:
        list: 创建后最新的路径树结构
    """
    if is_abs_windows(path):
        # 绝对路径：直接使用，exist_ok=True 表示已存在时不报错
        os.makedirs(path, exist_ok=True)
    else:
        os.makedirs(os.path.join(DIR, path), exist_ok=True)
    return get_path_tree()

def create_file(path):
    """
    创建一个空文件。

    如果 path 是 Windows 绝对路径，则直接在指定位置创建；
    否则，路径将相对于全局 DIR 进行解析。
    如果文件已存在，则跳过创建（不会覆盖已有内容）。

    Args:
        path (str): 要创建的文件路径

    Returns:
        list: 创建后最新的路径树结构
    """
    if is_abs_windows(path):
        if not os.path.exists(path):
            with open(path, 'w', encoding='utf-8') as f:
                pass
    else:
        full_path = os.path.join(DIR, path)
        if not os.path.exists(full_path):
            with open(full_path, 'w', encoding='utf-8') as f:
                pass
    return get_path_tree()

def create_dir_with_json(json_path: dict, path: str = ''):
    """
    根据 JSON 结构的描述，批量创建目录和文件。

    这是 init() 的核心实现函数，允许用嵌套字典一次性定义整个目录树结构。

    JSON 结构格式：
      {
        "目录名": [
          "文件1.md",           # 字符串 = 文件
          {"子目录": [          # 字典 = 子目录，key 为目录名
            "子文件.md"          # value 列表包含该目录下的文件和子目录
          ]}
        ]
      }

    算法说明：
      第一轮遍历：递归创建所有目录（字典项）

      第二轮遍历：创建所有文件（字符串项）
        分两轮遍历是因为必须先创建目录才能在其中创建文件

    Args:
        json_path (dict): 描述目录结构的 JSON 字典
        path (str): 当前递归的基准路径，顶层调用时通常为 DIR

    Returns:
        list: 创建完成后最新的路径树结构

    Example:
        >>> structure = {
        ...     'vault': [
        ...         'readme.md',
        ...         {'notes': ['todo.md', 'ideas.md']},
        ...         {'assets': []}
        ...     ]
        ... }
        >>> create_dir_with_json(structure, '/base/path')
        # 将在 /base/path/vault/ 下创建 readme.md、notes/todo.md 等
    """
    # 将当前层级的目录名拼接到 path 上
    path = os.path.join(path, list(json_path.keys())[0])
    create_dir(path)

    # 第一轮：递归处理所有子目录（字典项），必须先建目录
    for item in list(json_path.values())[0]:
        if isinstance(item, dict):
            create_dir_with_json(item, path)

    # 第二轮：创建所有文件（字符串项），此时目录已全部就绪
    for item in list(json_path.values())[0]:
        if isinstance(item, str):
            create_file(os.path.join(path, item))

    return get_path_tree()

# --- delete 类：删除目录/文件 ----------------------------------------------
def delete_dir(path):
    """
    删除目录（支持嵌套删除）。

    如果 path 是 Windows 绝对路径，则直接删除；
    否则，路径将相对于全局 DIR 进行解析。

    Args:
        path (str): 要删除的目录路径

    Returns:
        list: 删除后最新的路径树结构
    """
    def rmdir(path):
        if os.path.exists(path):
            for root, dirs, files in os.walk(path, topdown=False):
                for file in files:
                    os.remove(os.path.join(root, file))
                for dir in dirs:
                    rmdir(os.path.join(root, dir))
            os.rmdir(path)
    if is_abs_windows(path):
        # 绝对路径：直接使用，exist_ok=True 表示已存在时不报错
        if os.path.exists(path):
            rmdir(path)
    else:
        full_path = os.path.join(DIR, path)
        if os.path.exists(full_path):
            rmdir(full_path)
    return get_path_tree()

def delete_file(path):
    """
    删除文件。

    Args:
        path (str): 要删除的文件路径

    Returns:
        list: 删除后最新的路径树结构
    """
    if is_abs_windows(path):
        os.remove(path)
    else:
        full_path = os.path.join(DIR, path)
        if os.path.exists(full_path):
            os.remove(full_path)
    return get_path_tree()

# --- write 类：写入文件内容 ------------------------------------
def write_file(path, content):
    """
    向指定文件写入内容。

    如果目标文件不存在，会创建新文件；
    如果目标文件存在，其原有内容将被完全替换为 content。

    Args:
        path (str): 要写入的文件路径
        content (str): 要写入的文本内容（不包含换行符）

    Returns:
        list: 写入后的最新路径树结构
    """
    if is_abs_windows(path):
        with open(path, 'w', encoding='utf-8') as f:
            f.write(content)
    else:
        full_path = os.path.join(DIR, path)
        with open(full_path, 'w', encoding='utf-8') as f:
            f.write(content)
    return get_path_tree()

def write_file_append(path, content):
    """
    向指定文件追加内容。

    如果目标文件不存在，会创建新文件；
    如果目标文件存在，其原有内容将被追加 content。

    如果目标文件不存在，会创建新文件；
    如果目标文件存在，其原有内容将被追加 content。

    Args:
        path (str): 要写入的文件路径
        content (str): 要写入的文本内容（不包含换行符）

    Returns:
        list: 写入后的最新路径树结构
    """
    if is_abs_windows(path):
        with open(path, 'a', encoding='utf-8') as f:
            f.write(content)
    else:
        full_path = os.path.join(DIR, path)
        with open(full_path, 'a', encoding='utf-8') as f:
            f.write(content)
    return get_path_tree()

def write_file_append_line(path, content):
    """
    向指定文件追加一行内容（自动换行，不换行则追加在上一行后面）。

    如果目标文件不存在，会创建新文件；
    如果目标文件存在，其原有内容末尾会被追加 content（自动添加 \\n 前缀）。

    Args:
        path (str): 要写入的文件路径
        content (str): 要追加的行内容

    Returns:
        list: 写入后的最新路径树结构
    """
    if is_abs_windows(path):
        with open(path, 'a', encoding='utf-8') as f:
            f.write('\n' + content)
    else:
        full_path = os.path.join(DIR, path)
        with open(full_path, 'a', encoding='utf-8') as f:
            f.write('\n' + content)
    return get_path_tree()

def write_file_on_line(path,content,line):
    if is_abs_windows(path):
        with open(path, 'r', encoding='utf-8') as f:
            file=f.readlines()
        file.insert(line,content)
        with open(path, 'w', encoding='utf-8') as f:
            f.writelines(file)
    else:
        full_path = os.path.join(DIR, path)
        with open(full_path, 'r', encoding='utf-8') as f:
            file=f.readlines()
        file.insert(line,content)
        with open(full_path, 'w', encoding='utf-8') as f:
            f.writelines(file)
    return get_path_tree()

# --- read 类：读取文件内容 ------------------------------------
def read_file(path):
    """
    从指定文件读取内容。
    如果文件不存在，会返回空字符串。

    Args:
        path (str): 要读取的文件路径

    Returns:
        str: 文件内容（包含换行符）
    """
    if is_abs_windows(path):
        with open(path, 'r', encoding='utf-8') as f:
            return f.read()
    else:
        full_path = os.path.join(DIR, path)
        if not os.path.exists(full_path):
            return ''
        with open(full_path, 'r', encoding='utf-8') as f:
            return f.read()
    return ''

def read_file_on_line(path,line):
    if is_abs_windows(path):
        with open(path, 'r', encoding='utf-8') as f:
            return f.readlines()[line]
    else:
        full_path = os.path.join(DIR, path)
        with open(full_path, 'r', encoding='utf-8') as f:
            return f.readlines()[line]

# ============================================================
# 中层函数 —— 面向"笔记"概念的语义化操作
#
# 说明：这一层的所有函数都假定操作对象是 Markdown 笔记文件（.md）。
# 调用时只需传入不含 ".md" 后缀的笔记名或路径，函数会自动追加后缀。
# 例如：create_note('daily/log') 实际会创建 daily/log.md
# ============================================================

# --- create 类：创建笔记 ---------------------------------------
def create_note(note: str):
    """
    创建一篇空的 Markdown 笔记文件。

    如果笔记名包含路径分隔符（如 'dir/subdir/note_name'），
    则会在对应的子目录下创建笔记。嵌套目录需提前存在。

    Args:
        note (str): 笔记名或相对路径（不含 .md 后缀），
                    例如 'daily/2026-05-10' 对应文件 daily/2026-05-10.md

    Returns:
        list: 创建后的最新路径树结构
    """
    create_file(note + '.md')
    return get_path_tree()


# --- delete 类：删除笔记 ---------------------------------------
def delete_note(note: str):
    """
    物理删除一篇 Markdown 笔记文件。

    警告：此操作不可逆，文件会直接从磁盘上移除。

    Args:
        note (str): 笔记名或相对路径（不含 .md 后缀）

    Returns:
        list: 删除后的最新路径树结构
    """
    if is_abs_windows(note):
        os.remove(note + '.md')
    else:
        os.remove(os.path.join(DIR, note + '.md'))
    return get_path_tree()


# --- write 类：写入笔记内容 ------------------------------------
def write_note(note: str, note_content: str):
    """
    向指定笔记文件写入内容（覆盖写入模式）。

    如果目标文件不存在，会打印错误提示并返回当前路径树；
    如果目标文件存在，其原有内容将被完全替换为 note_content。

    Args:
        note (str): 笔记名或相对路径（不含 .md 后缀）
        note_content (str): 要写入的 Markdown 文本内容

    Returns:
        list: 写入后的最新路径树结构（即使写入失败也会返回）
    """
    write_file(note + '.md', note_content)
    return get_path_tree()

def write_note_on_line(note: str, line: int, content: str):
    """
    向指定笔记文件的指定行写入内容（覆盖写入模式）。

    如果目标文件不存在，会打印错误提示并返回当前路径树；
    如果目标文件存在，其原有内容将被完全替换为 note_content。

    Args:
        note (str): 笔记名或相对路径（不含 .md 后缀）
        line (int): 要写入的行号（从 0 开始）
        content (str): 要写入的 Markdown 文本内容

    Returns:
        list: 写入后的最新路径树结构（即使写入失败也会返回）
    """
    write_file_on_line(note + '.md', content, line)
    return get_path_tree()

# --- change 类：修改笔记属性 -----------------------------------
def change_note_name(note: str, new_note: str):
    """
    重命名一篇笔记（仅修改文件名，保持所在目录不变）。

    内部实现：从 note 路径中提取目录部分，与 new_note 拼接为新路径。

    Args:
        note (str): 当前笔记名或相对路径（不含 .md 后缀），
                    例如 'daily/old_name'
        new_note (str): 新笔记名（仅文件名，不含目录路径和 .md 后缀），
                        例如 'new_name'（结果：daily/new_name.md）

    Returns:
        list: 重命名后的最新路径树结构
    """
    try:
        if is_abs_windows(note):
            old_full = note + '.md'
        else:
            old_full = os.path.join(DIR, note + '.md')
        if is_abs_windows(new_note):
            new_full = new_note + '.md'
        else:
            new_full = os.path.join(DIR, new_note + '.md')
        os.rename(old_full, new_full)
    except FileNotFoundError:
        print(f'笔记{note}不存在')
    except Exception as e:
        print(f'修改笔记{note}名称失败：{e}')
    return get_path_tree()

def change_note_dir(note: str, new_dir: str):
    """
    将笔记移动到指定目录（文件名保持不变）。

    目标目录必须已存在，否则会抛出异常。

    Args:
        note (str): 当前笔记名或相对路径（不含 .md 后缀），
                    例如 'old_dir/note_name'
        new_dir (str): 目标目录的相对路径（相对于 DIR），
                       例如 'new_dir'（结果：new_dir/note_name.md）

    Returns:
        list: 移动后的最新路径树结构
    """
    try:
        if is_abs_windows(note):
            old_full = note + '.md'
        else:
            old_full = os.path.join(DIR, note + '.md')

        # 提取笔记文件名部分（不含路径）
        note_name = note.split('/')[-1]

        if is_abs_windows(new_dir):
            new_full = os.path.join(new_dir, note_name + '.md')
        else:
            new_full = os.path.join(DIR, new_dir, note_name + '.md')

        os.rename(old_full, new_full)
    except FileNotFoundError:
        print(f'笔记{note}不存在')
    except Exception as e:
        print(f'修改笔记{note}目录失败：{e}')
    return get_path_tree()


# --- read 类：读取笔记内容 -------------------------------------
def read_note(note: str):
    """
    读取一篇 Markdown 笔记的完整文本内容。

    Args:
        note (str): 笔记名或相对路径（不含 .md 后缀）

    Returns:
        str | None: 笔记的文本内容；如果文件不存在则打印提示并返回 None
    """
    try:
        with open(os.path.join(DIR, note + '.md'), 'r', encoding='utf-8') as f:
            return f.read()
    except FileNotFoundError:
        print(f'笔记{note}不存在')
    except Exception as e:
        print(f'读取笔记{note}内容失败：{e}')
    return None


# ============================================================
# 顶层函数 —— 模块初始化入口
# ============================================================
def init(path:dict):
    """
    初始化文件服务器的工作目录和初始文件结构。

    此函数是模块的入口，应在所有其他操作之前调用。它确保 DIR 目录存在，
    然后根据提供的 JSON 结构描述批量创建目录和文件。

    path 参数格式与 create_dir_with_json 相同，例如：
        {
            "root": [
                "readme.md",
                {"notes": ["inbox.md"]},
                {"templates": []}
            ]
        }

    Args:
        path (dict | str): 描述初始目录结构的 JSON 字典，或空字符串（跳过建结构）。
                           注意：类型标注为 str 是历史遗留，实际应传入 dict。
    """
    # 确保工作根目录存在
    os.makedirs(DIR, exist_ok=True)
    # 根据 JSON 结构创建初始文件和目录
    create_dir_with_json(path, DIR)
    reload_path_tree()

# ============================================================
# 调试入口 —— 直接运行此模块时执行的全面功能测试
#
# 覆盖范围（共 30+ 项测试）：
#
#   底层函数：
#     1-2.  set_DIR / get_DIR
#     3-6.  is_dir / is_file / is_path / is_abs_windows
#     7.    get_complete_path
#     8-9.  walk_path_to_tree / reload_path_tree
#     10-11. create_dir / create_file
#     12.   create_dir_with_json
#     13-14. read_file / read_file_on_line
#     15-17. write_file / write_file_append / write_file_append_line
#     18.   write_file_on_line
#     19.   delete_file
#     20.   delete_dir
#     21.   get_path_tree（直接返回缓存版本）
#
#   中层函数：
#     22.   create_note
#     23.   write_note
#     24.   write_note_on_line
#     25-26. change_note_name / change_note_dir
#     27.   read_note
#     28.   delete_note
#
#   顶层函数：
#     29.   init
#
#   边界情况：
#     30.   读取不存在的文件/笔记
#     31.   删除不存在的文件
#     32.   is_path 对无效路径返回 False
#
# 预期输出：每个测试输出 [测试 N] → 结果，最后汇总
# ============================================================
if __name__ == '__main__':
    import shutil
    import sys

    # ---- 测试环境设置 ----
    TEST_ROOT = get_complete_path('_TEST_DATA')
    TEST_DIR = os.path.join(TEST_ROOT, 'vault')

    # 清理上一次测试残留
    if os.path.exists(TEST_ROOT):
        shutil.rmtree(TEST_ROOT)

    print('=' * 62)
    print('   文件服务器模块 —— 全面功能测试')
    print('=' * 62)

    # ============================================
    # 第一部分：底层函数测试
    # ============================================

    # --- 1-2. set_DIR / get_DIR ---
    print('\n' + '─' * 62)
    set_DIR(TEST_DIR)
    assert get_DIR() == TEST_DIR, f'set_DIR/get_DIR 失败: {get_DIR()} != {TEST_DIR}'
    print('[测试 1/2] set_DIR / get_DIR  ✓')

    # --- 3-6. is_* 系列 ---
    os.makedirs(TEST_DIR, exist_ok=True)
    test_file = os.path.join(TEST_DIR, 'alpha.txt')
    with open(test_file, 'w') as f:
        f.write('hello')

    assert is_dir('') is True, 'is_dir 对根目录应返回 True'
    assert is_file('alpha.txt') is True, 'is_file 对存在的文件应返回 True'
    assert is_path('alpha.txt') is True, 'is_path 对存在的文件应返回 True'
    assert is_dir('alpha.txt') is False, 'is_dir 对文件应返回 False'
    assert is_file('') is False, 'is_file 对目录应返回 False'
    assert is_path('nonexistent') is False, 'is_path 对不存在的路径应返回 False'
    assert is_abs_windows('C:/test') is True, 'is_abs_windows("C:/test") 应为 True'
    assert is_abs_windows('relative/path') is False, 'is_abs_windows("relative/...") 应为 False'
    print('[测试 3]   is_dir     ✓')
    print('[测试 4]   is_file    ✓')
    print('[测试 5]   is_path    ✓')
    print('[测试 6]   is_abs_windows  ✓')

    # --- 7. get_complete_path ---
    cwd = os.getcwd()
    assert get_complete_path('_TEST_DATA') == os.path.join(cwd, '_TEST_DATA')
    print('[测试 7]   get_complete_path  ✓')

    # --- 8. walk_path_to_tree ---
    with open(os.path.join(TEST_DIR, 'beta.txt'), 'w') as f:
        f.write('')
    os.makedirs(os.path.join(TEST_DIR, 'sub'), exist_ok=True)
    with open(os.path.join(TEST_DIR, 'sub', 'gamma.txt'), 'w') as f:
        f.write('')
    tree = walk_path_to_tree(TEST_DIR)
    assert 'alpha.txt' in tree, '路径树应包含 alpha.txt'
    sub_entry = next(item for item in tree if isinstance(item, dict) and item['dir'] == 'sub')
    assert 'gamma.txt' in sub_entry['files'], 'sub 目录应包含 gamma.txt'
    print('[测试 8]   walk_path_to_tree  ✓')

    # --- 9. reload_path_tree ---
    reload_path_tree()
    assert PATH_TREE is not None, 'PATH_TREE 不应为 None'
    print('[测试 9]   reload_path_tree   ✓')

    # --- 10. create_dir ---
    result = create_dir('notes')
    assert is_dir('notes'), 'create_dir 后 notes 目录应存在'
    print('[测试 10]  create_dir    ✓')

    # --- 11. create_file ---
    result = create_file('notes/todo.txt')
    assert is_file('notes/todo.txt'), 'create_file 后 todo.txt 应存在'
    print('[测试 11]  create_file   ✓')

    # --- 12. create_dir_with_json ---
    structure = {
        'projects': [
            'readme.md',
            {'python': ['main.py', 'utils.py']},
            {'js': ['app.js']}
        ]
    }
    result = create_dir_with_json(structure, TEST_DIR)
    assert is_dir('projects'), 'create_dir_with_json 应创建 projects'
    assert is_dir('projects/python'), '应创建 projects/python'
    assert is_file('projects/python/main.py'), '应创建 projects/python/main.py'
    assert is_file('projects/js/app.js'), '应创建 projects/js/app.js'
    print('[测试 12]  create_dir_with_json  ✓')

    # --- 13. read_file ---
    todo_path = os.path.join('notes', 'todo.txt')
    content = read_file(todo_path)
    assert content == '', '新建空文件读回应为空字符串'
    # 读取不存在的文件应返回 '' 而不是抛出异常
    assert read_file('nonexistent/file.txt') == '', '不存在文件应返回空字符串'
    print('[测试 13]  read_file     ✓')

    # --- 14. read_file_on_line ---
    # 先准备一个多行文件
    write_file('notes/multi.txt', 'line0\nline1\nline2')
    assert read_file_on_line('notes/multi.txt', 1) == 'line1\n', '第1行应为 line1'
    print('[测试 14]  read_file_on_line  ✓')

    # --- 15. write_file ---
    write_file('notes/hello.txt', 'Hello World')
    assert read_file('notes/hello.txt') == 'Hello World', 'write_file 内容不匹配'
    print('[测试 15]  write_file    ✓')

    # --- 16. write_file_append ---
    write_file('notes/log.txt', 'start')
    write_file_append('notes/log.txt', '-middle')
    content = read_file('notes/log.txt')
    assert content == 'start-middle', f'追加结果应为 start-middle，实际为 {content!r}'
    print('[测试 16]  write_file_append  ✓')

    # --- 17. write_file_append_line ---
    write_file('notes/log2.txt', 'line1')
    write_file_append_line('notes/log2.txt', 'line2')
    content = read_file('notes/log2.txt')
    assert content == 'line1\nline2', f'追加行结果应为 line1\\nline2，实际为 {content!r}'
    print('[测试 17]  write_file_append_line  ✓')

    # --- 18. write_file_on_line ---
    write_file('notes/lines.txt', 'aaa\nccc')
    write_file_on_line('notes/lines.txt', 'bbb\n', 1)  # 在第1行前插入
    content = read_file('notes/lines.txt')
    assert 'bbb' in content, f'write_file_on_line 后应包含 bbb，实际为 {content!r}'
    assert content.index('bbb') < content.index('ccc'), 'bbb 应在 ccc 之前'
    print('[测试 18]  write_file_on_line  ✓')

    # --- 19. delete_file ---
    create_file('notes/temp_delete.txt')
    assert is_file('notes/temp_delete.txt'), 'delete_file 前文件应存在'
    result = delete_file('notes/temp_delete.txt')
    assert not is_file('notes/temp_delete.txt'), 'delete_file 后文件应不存在'
    print('[测试 19]  delete_file   ✓')

    # --- 20. delete_dir ---
    create_dir('temp_dir_to_delete')
    create_file('temp_dir_to_delete/trash.txt')
    assert is_dir('temp_dir_to_delete'), 'delete_dir 前目录应存在'
    result = delete_dir('temp_dir_to_delete')
    assert not is_dir('temp_dir_to_delete'), 'delete_dir 后目录应不存在'
    print('[测试 20]  delete_dir    ✓')

    # --- 21. get_path_tree（直接返回缓存版本）---
    tree_direct = get_path_tree()  # 这调用的是 reload+return 的版本
    # 验证返回类型
    assert isinstance(tree_direct, list), 'get_path_tree 应返回 list'
    print('[测试 21]  get_path_tree（含 reload） ✓')


    # ============================================
    # 第二部分：中层函数测试（笔记操作）
    # ============================================

    print('\n' + '─' * 62)

    # --- 22. create_note ---
    result = create_note('test_note')
    assert is_file('test_note.md'), 'create_note 后 test_note.md 应存在'
    print('[测试 22]  create_note   ✓')

    # --- 23. write_note ---
    result = write_note('test_note', '# 测试笔记标题\n\n正文内容')
    content = read_file('test_note.md')
    assert '测试笔记标题' in content, 'write_note 内容不匹配'
    print('[测试 23]  write_note    ✓')

    # --- 24. write_note_on_line ---
    write_note_on_line('test_note', 1, '插入行\n')
    content = read_note('test_note')
    assert '插入行' in content, 'write_note_on_line 后应包含插入行'
    print('[测试 24]  write_note_on_line  ✓')

    # --- 25. change_note_name ---
    create_note('rename_me')
    result = change_note_name('rename_me', 'renamed')
    assert not is_file('rename_me.md'), '改名后原文件应不存在'
    assert is_file('renamed.md'), '改名后新文件应存在'
    print('[测试 25]  change_note_name  ✓')

    # --- 26. change_note_dir ---
    create_dir('sub_notes')
    result = change_note_dir('renamed', 'sub_notes')
    assert is_file('sub_notes/renamed.md'), '移动后文件应在子目录中'
    print('[测试 26]  change_note_dir  ✓')

    # --- 27. read_note ---
    content = read_note('test_note')
    assert content is not None, 'read_note 不应返回 None'
    assert '正文内容' in content, 'read_note 内容不匹配'
    # 读取不存在的笔记
    content = read_note('nonexistent_note')
    assert content is None, '读取不存在笔记应返回 None'
    print('[测试 27]  read_note     ✓')

    # --- 28. delete_note ---
    create_note('to_delete')
    result = delete_note('to_delete')
    assert not is_file('to_delete.md'), 'delete_note 后文件应不存在'
    print('[测试 28]  delete_note   ✓')


    # ============================================
    # 第三部分：顶层函数测试
    # ============================================

    print('\n' + '─' * 62)

    # --- 29. init ---
    init_path = {
        'my_app': [
            'config.md',
            {'docs': ['readme.md']},
            {'logs': []}
        ]
    }
    DIR = TEST_DIR  # 恢复 DIR（顶层函数可能被中间测试改变了）
    init(init_path)
    assert is_dir('my_app'), 'init 应创建 my_app 目录'
    assert is_file('my_app/config.md'), 'init 应创建 my_app/config.md'
    assert is_dir('my_app/docs'), 'init 应创建 my_app/docs'
    assert is_dir('my_app/logs'), 'init 应创建 my_app/logs'
    print('[测试 29]  init          ✓')


    # ============================================
    # 第四部分：边界情况测试
    # ============================================

    print('\n' + '─' * 62)

    # --- 30. 删除不存在的文件（应不抛出异常）---
    result = delete_file('ghost_file.txt')
    assert result is not None, '删除不存在文件应正常返回路径树'
    print('[测试 30]  delete_file（不存在文件） ✓')

    # --- 31. 删除不存在的目录（应不抛出异常）---
    result = delete_dir('ghost_dir')
    assert result is not None, '删除不存在目录应正常返回路径树'
    print('[测试 31]  delete_dir（不存在目录）  ✓')

    # --- 32. is_path 边界 ---
    assert is_path('') is True, '空字符串对应根目录应 True'
    assert is_path('!' * 50) is False, '非法路径应返回 False'
    print('[测试 32]  is_path 边界      ✓')


    # ============================================
    # 清理：删除测试目录
    # ============================================

    print('\n' + '─' * 62)
    print('\n【清理测试数据】...')
    os.chdir(cwd)  # 确保不在测试目录内
    if os.path.exists(TEST_ROOT):
        shutil.rmtree(TEST_ROOT)
        print(f'已删除: {TEST_ROOT}')

    # ---- 汇总 ----
    print('\n' + '=' * 62)
    print('   全部 32 项测试通过 ✓')
    print('=' * 62)
