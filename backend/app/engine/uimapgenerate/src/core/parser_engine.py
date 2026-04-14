import os

AVAILABLE = False
UNAVAILABLE_REASON = ""

try:
    from tree_sitter import Language, Parser  # type: ignore
except Exception as e:
    Language = None  # type: ignore
    Parser = None  # type: ignore
    UNAVAILABLE_REASON = f"tree_sitter import failed: {e}"

# 1. 获取当前文件的绝对路径
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))

# 2. 使用 normpath 彻底解析 ".."
# 它会将 /home/laz/code/AIST/src/core/../../config 转换成 /home/laz/code/AIST/config
LIB_PATH = os.path.normpath(os.path.join(CURRENT_DIR, "..", "..", "config", "tree-sitter-languages", "languages.so"))

# 调试打印：如果还报错，你可以看到 Python 到底在找哪个绝对路径
# print(f"DEBUG: 尝试加载库文件: {LIB_PATH}")

JAVA_LANG = None
KOTLIN_LANG = None
parser = None

if Language is not None and Parser is not None:
    if not os.path.exists(LIB_PATH):
        UNAVAILABLE_REASON = f"languages.so not found at {LIB_PATH}"
    else:
        try:
            # 3. 加载语言
            JAVA_LANG = Language(LIB_PATH, "java")
            KOTLIN_LANG = Language(LIB_PATH, "kotlin")
            parser = Parser()
            AVAILABLE = True
        except Exception as e:
            UNAVAILABLE_REASON = f"failed to init tree-sitter: {e}"

def set_language(file_path):
    if not AVAILABLE or parser is None:
        raise RuntimeError(f"Tree-sitter unavailable: {UNAVAILABLE_REASON}")
    if file_path.endswith(".java"):
        parser.set_language(JAVA_LANG)
    elif file_path.endswith(".kt") or file_path.endswith(".kotlin"):
        parser.set_language(KOTLIN_LANG)