#!/usr/bin/env python3
"""
自选股管理模块 V2.4
- 批量导入导出（TXT/CSV）
- 自选股分组（短线/中线/行业）
- 实时预警（涨跌幅、换手率、热搜、资金异动）
- 每日简报
"""

import json
import os
import csv
from datetime import datetime
from utils.common import log, CACHE_DIR

WATCHLIST_DIR = os.path.join(CACHE_DIR, "watchlist")


class WatchlistManager:
    """自选股管理器"""
    
    def __init__(self, config_path=None):
        self.config_path = config_path or os.path.join(WATCHLIST_DIR, "watchlist.json")
        self.data = self._load()
    
    def _load(self):
        """加载自选股配置"""
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return {"groups": {"默认": []}, "alerts": [], "history": []}
    
    def _save(self):
        """保存自选股配置"""
        os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
        with open(self.config_path, "w", encoding="utf-8") as f:
            json.dump(self.data, f, ensure_ascii=False, indent=2)
    
    # ============================================================
    # 基础操作
    # ============================================================
    def add(self, code, name="", group="默认"):
        """添加自选股"""
        if group not in self.data["groups"]:
            self.data["groups"][group] = []
        # 去重
        existing = [s["code"] for s in self.data["groups"][group]]
        if code in existing:
            return False
        self.data["groups"][group].append({
            "code": code,
            "name": name,
            "added_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        })
        self._save()
        return True
    
    def remove(self, code, group=None):
        """移除自选股"""
        groups = [group] if group else list(self.data["groups"].keys())
        removed = False
        for g in groups:
            if g in self.data["groups"]:
                before = len(self.data["groups"][g])
                self.data["groups"][g] = [s for s in self.data["groups"][g] if s["code"] != code]
                if len(self.data["groups"][g]) < before:
                    removed = True
        if removed:
            self._save()
        return removed
    
    def list(self, group=None):
        """列出自选股"""
        if group:
            return self.data["groups"].get(group, [])
        all_stocks = []
        for g, stocks in self.data["groups"].items():
            for s in stocks:
                s["group"] = g
                all_stocks.append(s)
        return all_stocks
    
    def get_codes(self):
        """获取所有自选股代码列表"""
        codes = []
        for stocks in self.data["groups"].values():
            for s in stocks:
                codes.append(s["code"])
        return list(set(codes))
    
    def get_names(self):
        """获取所有自选股名称列表"""
        names = []
        for stocks in self.data["groups"].values():
            for s in stocks:
                if s.get("name"):
                    names.append(s["name"])
        return names
    
    # ============================================================
    # 分组管理
    # ============================================================
    def create_group(self, name):
        """创建分组"""
        if name not in self.data["groups"]:
            self.data["groups"][name] = []
            self._save()
            return True
        return False
    
    def delete_group(self, name):
        """删除分组"""
        if name in self.data["groups"] and name != "默认":
            del self.data["groups"][name]
            self._save()
            return True
        return False
    
    def move_stock(self, code, from_group, to_group):
        """移动股票到其他分组"""
        stock = None
        for s in self.data["groups"].get(from_group, []):
            if s["code"] == code:
                stock = s
                break
        if stock:
            self.remove(code, from_group)
            self.add(code, stock.get("name", ""), to_group)
            return True
        return False
    
    # ============================================================
    # 批量导入导出
    # ============================================================
    def import_from_txt(self, filepath):
        """从 TXT 文件导入（每行一个：代码 或 代码,名称）"""
        imported = 0
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    parts = line.split(",")
                    code = parts[0].strip()
                    name = parts[1].strip() if len(parts) > 1 else ""
                    if code:
                        if self.add(code, name):
                            imported += 1
        except Exception as e:
            log(f"⚠️  TXT导入失败: {e}")
        return imported
    
    def import_from_csv(self, filepath):
        """从 CSV 文件导入（需要 code 列，可选 name 列）"""
        imported = 0
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    code = row.get("code", row.get("代码", "")).strip()
                    name = row.get("name", row.get("名称", "")).strip()
                    if code:
                        if self.add(code, name):
                            imported += 1
        except Exception as e:
            log(f"⚠️  CSV导入失败: {e}")
        return imported
    
    def export_to_txt(self, filepath, group=None):
        """导出为 TXT 文件"""
        stocks = self.list(group)
        try:
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(f"# 自选股导出 {datetime.now().strftime('%Y-%m-%d %H:%M')}\n")
                for s in stocks:
                    f.write(f"{s['code']},{s.get('name', '')}\n")
            return len(stocks)
        except Exception as e:
            log(f"⚠️  TXT导出失败: {e}")
            return 0
    
    def export_to_csv(self, filepath, group=None):
        """导出为 CSV 文件"""
        stocks = self.list(group)
        try:
            with open(filepath, "w", encoding="utf-8", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=["code", "name", "group", "added_at"])
                writer.writeheader()
                for s in stocks:
                    writer.writerow(s)
            return len(stocks)
        except Exception as e:
            log(f"⚠️  CSV导出失败: {e}")
            return 0
    
    # ============================================================
    # 预警系统
    # ============================================================
    def add_alert(self, code, alert_type, threshold, group="默认"):
        """
        添加预警规则
        alert_type: "change_pct" | "turnover" | "hotsearch" | "fund_flow"
        threshold: 阈值（如 5 表示涨跌幅>=5%）
        """
        alert = {
            "code": code,
            "type": alert_type,
            "threshold": threshold,
            "group": group,
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "triggered": False,
        }
        self.data["alerts"].append(alert)
        self._save()
        return True
    
    def check_alerts(self, stock_data):
        """
        检查预警是否触发
        stock_data: dict of {code: {price, change_pct, turnover, ...}}
        返回触发的预警列表
        """
        triggered = []
        for alert in self.data["alerts"]:
            code = alert["code"]
            if code not in stock_data:
                continue
            data = stock_data[code]
            at = alert["type"]
            threshold = alert["threshold"]
            
            fire = False
            if at == "change_pct" and abs(data.get("change_pct", 0)) >= threshold:
                fire = True
            elif at == "turnover" and data.get("turnover", 0) >= threshold:
                fire = True
            elif at == "hotsearch" and data.get("is_hotsearch", False):
                fire = True
            elif at == "fund_flow" and abs(data.get("main_net_flow", 0)) >= threshold:
                fire = True
            
            if fire:
                alert["triggered"] = True
                alert["triggered_at"] = datetime.now().strftime("%Y-%m-%d %H:%M")
                triggered.append(alert)
        
        if triggered:
            self._save()
        return triggered
    
    # ============================================================
    # 每日简报
    # ============================================================
    def generate_daily_brief(self, market_data, hotsearch_data, capital_data):
        """生成自选股每日简报"""
        codes = self.get_codes()
        names = self.get_names()
        
        brief = {
            "date": datetime.now().strftime("%Y-%m-%d"),
            "watchlist_count": len(codes),
            "stocks": [],
            "related_hotsearch": [],
            "capital_summary": {},
        }
        
        # 筛选自选股行情
        if market_data:
            for stock in market_data:
                if stock.get("code") in codes or stock.get("name") in names:
                    brief["stocks"].append(stock)
        
        # 筛选自选股相关热搜
        if hotsearch_data:
            for item in hotsearch_data:
                for name in names:
                    if name in item.get("keyword", ""):
                        brief["related_hotsearch"].append(item)
                        break
        
        # 筛选自选股资金数据
        if capital_data:
            for code in codes:
                if code in capital_data:
                    brief["capital_summary"][code] = capital_data[code]
        
        return brief
