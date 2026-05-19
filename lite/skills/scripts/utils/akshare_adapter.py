#!/usr/bin/env python3
"""
AKShare 适配层 V2.4
- 隔离版本变更带来的接口兼容问题
- 接口降级机制
- 友好错误提示
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    import akshare as ak
    import warnings
    warnings.filterwarnings("ignore")
    HAS_AKSHARE = True
    AK_VERSION = getattr(ak, "__version__", "unknown")
except ImportError:
    HAS_AKSHARE = False
    AK_VERSION = None

from utils.common import log


class AKShareAdapter:
    """AKShare 适配器，提供版本兼容和降级机制"""
    
    def __init__(self):
        self.available = HAS_AKSHARE
        self.version = AK_VERSION
        self._call_count = 0
        self._fail_count = 0
    
    def check_version(self):
        """检查 AKShare 版本"""
        if not self.available:
            return {
                "available": False,
                "error": "akshare 未安装",
                "fix": "pip3 install akshare",
            }
        try:
            from packaging.version import Version
            if self.version and Version(self.version) < Version("1.10.0"):
                return {
                    "available": True,
                    "version": self.version,
                    "warning": f"akshare 版本 {self.version} 过低，建议升级至 >=1.10.0",
                    "fix": "pip3 install --upgrade akshare",
                }
        except Exception:
            pass
        return {"available": True, "version": self.version}
    
    def call(self, func_name, *args, fallback=None, **kwargs):
        """
        安全调用 AKShare 函数
        - 自动捕获异常
        - 支持降级 fallback
        - 记录调用统计
        """
        self._call_count += 1
        if not self.available:
            self._fail_count += 1
            if fallback is not None:
                return fallback
            return None
        
        try:
            func = getattr(ak, func_name, None)
            if func is None:
                log(f"⚠️  AKShare 接口 {func_name} 不存在")
                self._fail_count += 1
                return fallback if fallback is not None else None
            
            result = func(*args, **kwargs)
            return result
        except Exception as e:
            self._fail_count += 1
            error_msg = str(e)
            
            # 友好错误提示
            if "rate" in error_msg.lower() or "limit" in error_msg.lower():
                log(f"⚠️  AKShare 接口 {func_name} 限流，将使用缓存数据")
            elif "timeout" in error_msg.lower():
                log(f"⚠️  AKShare 接口 {func_name} 超时")
            elif "key" in error_msg.lower() or "column" in error_msg.lower():
                log(f"⚠️  AKShare 接口 {func_name} 列名变更，请升级 akshare: pip3 install --upgrade akshare")
            else:
                log(f"⚠️  AKShare 接口 {func_name} 调用失败: {e}")
            
            return fallback if fallback is not None else None
    
    def stats(self):
        """返回调用统计"""
        return {
            "total_calls": self._call_count,
            "failed_calls": self._fail_count,
            "success_rate": round((self._call_count - self._fail_count) / max(1, self._call_count) * 100, 1),
        }


# 全局实例
adapter = AKShareAdapter()
