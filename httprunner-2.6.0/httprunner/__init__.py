"""
1.加载ENV文件时，加入对注释#
2.提取值时，优先使用jsonpath（对*号等的支持，如$.data.list.*.name）
"""


__version__ = "2.6.0"
__description__ = "One-stop solution for HTTP(S) testing."

__all__ = ["__version__", "__description__"]
