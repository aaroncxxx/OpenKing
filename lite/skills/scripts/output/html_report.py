#!/usr/bin/env python3
"""
交互式 HTML 报告生成 V2.2
- 大盘走势图
- 板块资金流向图
- 热搜热度排名
- 北向资金趋势
- 内嵌 Chart.js 图表
"""

from datetime import datetime
from utils.common import format_hot, format_yi


def generate_html_report(data):
    """生成交互式 HTML 报告"""
    title = f"A股热搜分析报告 v2.4 — {datetime.now().strftime('%Y-%m-%d %H:%M')}"

    # 大盘数据
    market_labels = []
    market_values = []
    for idx in data.get("market", []):
        market_labels.append(idx["name"])
        market_values.append(idx["change_pct"])

    # 板块数据
    sector_labels = []
    sector_values = []
    for s in data.get("sectors", [])[:10]:
        sector_labels.append(s["name"])
        sector_values.append(s["change_pct"])

    # 热搜数据
    hot_labels = []
    hot_values = []
    for item in data.get("stock_hot", [])[:10]:
        hot_labels.append(item["keyword"])
        hot_values.append(item.get("hot", 0))

    # 北向资金
    nb = data.get("northbound", {})
    nb_net = nb.get("合计", {}).get("net", 0)
    nb_sh = nb.get("沪股通", {}).get("net", 0)
    nb_sz = nb.get("深股通", {}).get("net", 0)

    # 恐慌贪婪
    fg = data.get("fear_greed", {})
    fg_index = fg.get("index", 50)
    fg_level = fg.get("level", "中性")

    # 情绪
    stats = data.get("stats", {})
    up = stats.get("up", 0)
    down = stats.get("down", 0)
    flat = stats.get("flat", 0)

    # 涨停/跌停
    zt_dt = data.get("zt_dt", {})
    zt_list = zt_dt.get("涨停", [])
    dt_list = zt_dt.get("跌停", [])

    # 主力资金
    mf = data.get("main_force", {})
    mf_items = []
    for k in ["超大单", "大单", "中单", "小单"]:
        if k in mf:
            mf_items.append({"name": k, "value": mf[k]})

    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{title}</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
<style>
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #0d1117; color: #c9d1d9; padding: 20px; }}
.header {{ text-align: center; margin-bottom: 30px; }}
.header h1 {{ color: #58a6ff; font-size: 24px; }}
.header p {{ color: #8b949e; margin-top: 8px; }}
.grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(400px, 1fr)); gap: 20px; max-width: 1400px; margin: 0 auto; }}
.card {{ background: #161b22; border: 1px solid #30363d; border-radius: 12px; padding: 20px; }}
.card h2 {{ color: #58a6ff; font-size: 16px; margin-bottom: 15px; display: flex; align-items: center; gap: 8px; }}
.card.full {{ grid-column: 1 / -1; }}
.up {{ color: #3fb950; }}
.down {{ color: #f85149; }}
.flat {{ color: #8b949e; }}
.stat-row {{ display: flex; justify-content: space-between; padding: 8px 0; border-bottom: 1px solid #21262d; }}
.stat-row:last-child {{ border-bottom: none; }}
.stat-label {{ color: #8b949e; }}
.stat-value {{ font-weight: 600; }}
.gauge {{ width: 200px; height: 100px; margin: 0 auto; position: relative; }}
.gauge-bg {{ width: 200px; height: 100px; border-radius: 100px 100px 0 0; background: conic-gradient(from 0.75turn, #f85149, #d29922, #3fb950); position: relative; overflow: hidden; }}
.gauge-mask {{ position: absolute; width: 160px; height: 80px; background: #161b22; border-radius: 80px 80px 0 0; bottom: 0; left: 20px; }}
.gauge-value {{ position: absolute; bottom: 10px; width: 200px; text-align: center; font-size: 28px; font-weight: bold; }}
.gauge-label {{ text-align: center; color: #8b949e; margin-top: 5px; }}
table {{ width: 100%; border-collapse: collapse; }}
th {{ text-align: left; color: #8b949e; font-weight: 500; padding: 8px; border-bottom: 1px solid #30363d; }}
td {{ padding: 8px; border-bottom: 1px solid #21262d; }}
.badge {{ display: inline-block; padding: 2px 8px; border-radius: 12px; font-size: 12px; }}
.badge-hot {{ background: #f8514922; color: #f85149; }}
.badge-up {{ background: #3fb95022; color: #3fb950; }}
.badge-down {{ background: #f8514922; color: #f85149; }}
.chart-container {{ position: relative; height: 300px; }}
.footer {{ text-align: center; color: #484f58; margin-top: 30px; font-size: 13px; }}
</style>
</head>
<body>
<div class="header">
  <h1>📊 {title}</h1>
  <p>多平台热搜 + 资金分析 + 情绪指标</p>
</div>

<div class="grid">
  <!-- 恐慌贪婪指数 -->
  <div class="card">
    <h2>🎯 恐慌贪婪指数</h2>
    <div class="gauge">
      <div class="gauge-bg"><div class="gauge-mask"></div></div>
      <div class="gauge-value">{fg_index}</div>
    </div>
    <div class="gauge-label">{fg_level}</div>
  </div>

  <!-- 市场情绪 -->
  <div class="card">
    <h2>📈 市场情绪</h2>
    <div class="stat-row"><span class="stat-label">上涨</span><span class="stat-value up">{up} 家</span></div>
    <div class="stat-row"><span class="stat-label">下跌</span><span class="stat-value down">{down} 家</span></div>
    <div class="stat-row"><span class="stat-label">平盘</span><span class="stat-value flat">{flat} 家</span></div>
    <div class="stat-row"><span class="stat-label">涨停</span><span class="stat-value up">{len(zt_list)} 家</span></div>
    <div class="stat-row"><span class="stat-label">跌停</span><span class="stat-value down">{len(dt_list)} 家</span></div>
    <div class="stat-row"><span class="stat-label">北向净流入</span><span class="stat-value {'up' if nb_net > 0 else 'down'}">{format_yi(nb_net)}</span></div>
  </div>

  <!-- 大盘走势 -->
  <div class="card full">
    <h2>📊 大盘涨跌</h2>
    <div class="chart-container"><canvas id="marketChart"></canvas></div>
  </div>

  <!-- 板块排行 -->
  <div class="card">
    <h2>🔥 热门板块 TOP10</h2>
    <div class="chart-container"><canvas id="sectorChart"></canvas></div>
  </div>

  <!-- 热搜排行 -->
  <div class="card">
    <h2>🔍 A股热搜 TOP10</h2>
    <div class="chart-container"><canvas id="hotChart"></canvas></div>
  </div>

  <!-- 北向资金 -->
  <div class="card">
    <h2>🌊 北向资金</h2>
    <div class="stat-row"><span class="stat-label">合计净流入</span><span class="stat-value {'up' if nb_net > 0 else 'down'}">{format_yi(nb_net)}</span></div>
    <div class="stat-row"><span class="stat-label">沪股通</span><span class="stat-value {'up' if nb_sh > 0 else 'down'}">{format_yi(nb_sh)}</span></div>
    <div class="stat-row"><span class="stat-label">深股通</span><span class="stat-value {'up' if nb_sz > 0 else 'down'}">{format_yi(nb_sz)}</span></div>
  </div>

  <!-- 主力资金 -->
  <div class="card">
    <h2>💰 主力资金拆分</h2>
    <div class="chart-container"><canvas id="fundChart"></canvas></div>
  </div>

  <!-- 涨停板 -->
  <div class="card full">
    <h2>🟢 涨停板 TOP</h2>
    <table>
      <tr><th>股票</th><th>代码</th><th>涨跌幅</th><th>涨停原因</th></tr>
      {''.join(f'<tr><td>{z["name"]}</td><td>{z["code"]}</td><td class="up">{z["change_pct"]:+.1f}%</td><td>{z.get("reason","")}</td></tr>' for z in zt_list[:10])}
    </table>
  </div>

  <!-- 北向十大成交股 -->
  {"".join(f'''
  <div class="card full">
    <h2>🏆 北向十大成交股</h2>
    <table>
      <tr><th>股票</th><th>代码</th><th>净买入</th></tr>
      {"".join(f'<tr><td>{s["name"]}</td><td>{s["code"]}</td><td class="{"up" if s["net_buy"]>0 else "down"}">{format_yi(s["net_buy"])}</td></tr>' for s in data.get("northbound_top10",[])[:10])}
    </table>
  </div>''' if data.get("northbound_top10") else "")}

  <!-- 龙虎榜 -->
  {"".join(f'''
  <div class="card full">
    <h2>🐉 龙虎榜</h2>
    <table>
      <tr><th>股票</th><th>代码</th><th>涨跌幅</th><th>净买入</th><th>原因</th></tr>
      {"".join(f'<tr><td>{d["name"]}</td><td>{d["code"]}</td><td class="{"up" if d["change_pct"]>0 else "down"}">{d["change_pct"]:+.1f}%</td><td class="{"up" if d["net_buy"]>0 else "down"}">{format_yi(d["net_buy"])}</td><td>{d.get("reason","")}</td></tr>' for d in data.get("dragon_tiger",[])[:10])}
    </table>
  </div>''' if data.get("dragon_tiger") else "")}
</div>

<div class="footer">
  <p>Generated by A股分析 v2.4 | {datetime.now().strftime("%Y-%m-%d %H:%M")}</p>
</div>

<script>
// 大盘图
new Chart(document.getElementById('marketChart'), {{
  type: 'bar',
  data: {{
    labels: {market_labels},
    datasets: [{{ label: '涨跌幅%', data: {market_values},
      backgroundColor: {market_values}.map(v => v >= 0 ? '#3fb950' : '#f85149'),
      borderRadius: 6 }}]
  }},
  options: {{ responsive: true, maintainAspectRatio: false, plugins: {{ legend: {{ display: false }} }} }}
}});

// 板块图
new Chart(document.getElementById('sectorChart'), {{
  type: 'bar',
  data: {{
    labels: {sector_labels},
    datasets: [{{ label: '涨跌幅%', data: {sector_values},
      backgroundColor: {sector_values}.map(v => v >= 0 ? '#3fb950' : '#f85149'),
      borderRadius: 4 }}]
  }},
  indexAxis: 'y',
  options: {{ responsive: true, maintainAspectRatio: false, plugins: {{ legend: {{ display: false }} }} }}
}});

// 热搜图
new Chart(document.getElementById('hotChart'), {{
  type: 'bar',
  data: {{
    labels: {hot_labels},
    datasets: [{{ label: '热度', data: {hot_values},
      backgroundColor: '#f0883e', borderRadius: 4 }}]
  }},
  indexAxis: 'y',
  options: {{ responsive: true, maintainAspectRatio: false, plugins: {{ legend: {{ display: false }} }} }}
}});

// 主力资金图
new Chart(document.getElementById('fundChart'), {{
  type: 'doughnut',
  data: {{
    labels: {[f'"{m["name"]}"' for m in mf_items]},
    datasets: [{{ data: {[abs(m["value"]) for m in mf_items]},
      backgroundColor: ['#58a6ff', '#3fb950', '#d29922', '#f0883e'] }}]
  }},
  options: {{ responsive: true, maintainAspectRatio: false }}
}});
</script>
</body>
</html>"""

    return html
