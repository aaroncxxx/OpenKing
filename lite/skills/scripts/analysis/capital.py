#!/usr/bin/env python3
"""
资金分析模块 V2.4
- 北向资金升级：十大成交股、行业流向、持仓变动Top10
- 主力/游资/散户资金拆分
- 龙虎榜集成
- 大单/中单/小单成交占比
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    import akshare as ak
    import warnings
    warnings.filterwarnings("ignore")
    HAS_AKSHARE = True
except ImportError:
    HAS_AKSHARE = False

from utils.common import log, format_yi


class CapitalAnalyzer:
    """资金流向分析器"""
    
    def __init__(self):
        self.has_ak = HAS_AKSHARE
    
    # ============================================================
    # 北向资金升级
    # ============================================================
    def fetch_northbound_flow(self):
        """北向资金基础数据（沪股通/深股通净买入）"""
        if not self.has_ak:
            return {}
        result = {"沪股通": {}, "深股通": {}, "合计": {}}
        try:
            df = ak.stock_hsgt_north_net_flow_in_em()
            if df is not None and not df.empty:
                last_row = df.iloc[-1]
                result["date"] = str(last_row.get("date", ""))
                result["north_net"] = round(float(last_row.get("value", 0)), 2)
        except Exception:
            pass
        try:
            df2 = ak.stock_hsgt_fund_flow_summary_em()
            if df2 is not None and not df2.empty:
                last = df2.iloc[-1]
                for prefix, key in [("沪股通", "沪股通"), ("深股通", "深股通")]:
                    try:
                        result[key] = {
                            "buy": round(float(last.get(f"{prefix}-买入", 0)), 2),
                            "sell": round(float(last.get(f"{prefix}-卖出", 0)), 2),
                            "net": round(float(last.get(f"{prefix}-净买入", 0)), 2),
                        }
                    except (ValueError, TypeError):
                        result[key] = {"buy": 0, "sell": 0, "net": 0}
                hn = result["沪股通"].get("net", 0)
                sn = result["深股通"].get("net", 0)
                result["合计"]["net"] = round(hn + sn, 2)
        except Exception:
            pass
        return result
    
    def fetch_northbound_top10(self):
        """北向资金十大成交股"""
        if not self.has_ak:
            return []
        try:
            df = ak.stock_hsgt_north_acc_flow_in_em(symbol="北向资金")
            if df is not None and not df.empty:
                result = []
                for _, row in df.head(10).iterrows():
                    result.append({
                        "code": str(row.get("代码", "")),
                        "name": str(row.get("名称", "")),
                        "net_buy": round(float(row.get("净买入", 0)), 2),
                        "buy": round(float(row.get("买入", 0)), 2),
                        "sell": round(float(row.get("卖出", 0)), 2),
                    })
                return result
        except Exception as e:
            log(f"⚠️  北向十大成交股获取失败: {e}")
        return []
    
    def fetch_northbound_industry_flow(self):
        """北向资金行业流向分布"""
        if not self.has_ak:
            return []
        try:
            df = ak.stock_hsgt_north_industry_flow_em()
            if df is not None and not df.empty:
                result = []
                for _, row in df.head(15).iterrows():
                    result.append({
                        "industry": str(row.get("行业", "")),
                        "net_buy": round(float(row.get("净买入", 0)), 2),
                        "buy": round(float(row.get("买入", 0)), 2),
                        "sell": round(float(row.get("卖出", 0)), 2),
                    })
                return result
        except Exception as e:
            log(f"⚠️  北向行业流向获取失败: {e}")
        return []
    
    def fetch_northbound_holding_change(self):
        """北向资金持仓变动Top10"""
        if not self.has_ak:
            return []
        try:
            df = ak.stock_hsgt_hold_stock_em(market="北向", indicator="今日排行")
            if df is not None and not df.empty:
                result = []
                for _, row in df.head(10).iterrows():
                    result.append({
                        "code": str(row.get("代码", "")),
                        "name": str(row.get("名称", "")),
                        "holding": round(float(row.get("持股数量", 0)), 2),
                        "holding_mv": round(float(row.get("持股市值", 0)), 2),
                        "change": round(float(row.get("持股变动", 0)), 2),
                        "ratio": round(float(row.get("持股占比", 0)), 2),
                    })
                return result
        except Exception as e:
            log(f"⚠️  北向持仓变动获取失败: {e}")
        return []
    
    # ============================================================
    # 主力/游资/散户资金拆分
    # ============================================================
    def fetch_main_force_flow(self):
        """主力/游资/散户资金流向统计"""
        if not self.has_ak:
            return {}
        result = {}
        try:
            # 个股资金流向
            df = ak.stock_individual_fund_flow_rank(indicator="今日")
            if df is not None and not df.empty:
                # 按资金类型分类统计
                total_main = 0
                total_hot = 0
                total_retail = 0
                for _, row in df.iterrows():
                    try:
                        main_net = float(row.get("主力净流入-净额", 0))
                        total_main += main_net
                    except (ValueError, TypeError):
                        pass
                result["主力净流入"] = round(total_main, 2)
                result["个股数量"] = len(df)
        except Exception as e:
            log(f"⚠️  主力资金获取失败: {e}")
        
        # 大单/中单/小单统计
        try:
            df2 = ak.stock_market_fund_flow()
            if df2 is not None and not df2.empty:
                last = df2.iloc[-1]
                result["超大单"] = round(float(last.get("超大单", 0)), 2) if "超大单" in last.index else 0
                result["大单"] = round(float(last.get("大单", 0)), 2) if "大单" in last.index else 0
                result["中单"] = round(float(last.get("中单", 0)), 2) if "中单" in last.index else 0
                result["小单"] = round(float(last.get("小单", 0)), 2) if "小单" in last.index else 0
        except Exception as e:
            log(f"⚠️  大单统计获取失败: {e}")
        
        return result
    
    def fetch_single_stock_fund_flow(self, code):
        """单只股票资金流向详情"""
        if not self.has_ak:
            return {}
        try:
            df = ak.stock_individual_fund_flow(stock=code, market="sh" if code.startswith("6") else "sz")
            if df is not None and not df.empty:
                last = df.iloc[-1]
                return {
                    "主力净流入": round(float(last.get("主力净流入-净额", 0)), 2),
                    "主力净流入占比": round(float(last.get("主力净流入-净占比", 0)), 2),
                    "超大单净流入": round(float(last.get("超大单净流入-净额", 0)), 2),
                    "大单净流入": round(float(last.get("大单净流入-净额", 0)), 2),
                    "中单净流入": round(float(last.get("中单净流入-净额", 0)), 2),
                    "小单净流入": round(float(last.get("小单净流入-净额", 0)), 2),
                }
        except Exception as e:
            log(f"⚠️  个股资金流向获取失败: {e}")
        return {}
    
    # ============================================================
    # 龙虎榜
    # ============================================================
    def fetch_dragon_tiger(self):
        """龙虎榜数据"""
        if not self.has_ak:
            return []
        try:
            from datetime import datetime
            today = datetime.now().strftime("%Y%m%d")
            df = ak.stock_lhb_detail_em(start_date=today, end_date=today)
            if df is not None and not df.empty:
                result = []
                for _, row in df.head(15).iterrows():
                    result.append({
                        "code": str(row.get("代码", "")),
                        "name": str(row.get("名称", "")),
                        "change_pct": round(float(row.get("涨跌幅", 0)), 2),
                        "net_buy": round(float(row.get("龙虎榜净买额", 0)), 2),
                        "buy": round(float(row.get("龙虎榜买入额", 0)), 2),
                        "sell": round(float(row.get("龙虎榜卖出额", 0)), 2),
                        "reason": str(row.get("上榜原因", "")),
                    })
                return result
        except Exception as e:
            log(f"⚠️  龙虎榜获取失败: {e}")
        return []
