"""应用主包。"""

# 修复 passlib 与新版本 bcrypt 的兼容性问题
try:
    import bcrypt
    if not hasattr(bcrypt, "__about__"):
        class DummyAbout:
            __version__ = getattr(bcrypt, "__version__", "4.0.0")
        bcrypt.__about__ = DummyAbout()
except ImportError:
    pass
