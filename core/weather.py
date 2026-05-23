"""天气数据工具 v2.9.6 — Open-Meteo API（免费，无需 API Key，毫米级降雨量）

支持：
  - 逐小时降水量（mm）过去24h + 未来6h
  - 降雨概率、温度、湿度、风速
  - 广东省21地级市精确坐标
  - 全国主要城市通用坐标
"""
import urllib.request
import json
import time
from datetime import datetime, timedelta, timezone
from core.logger import get_logger

log = get_logger("weather")

# Open-Meteo API（免费，无需 Key）
OPEN_METEO_URL = (
    "https://api.open-meteo.com/v1/forecast"
    "?latitude={lat}&longitude={lon}"
    "&hourly=precipitation,precipitation_probability,temperature_2m,relative_humidity_2m,wind_speed_10m"
    "&past_hours=24&forecast_hours=6"
    "&timezone=Asia/Shanghai"
)

# ── 广东省21地级市坐标 ──
GUANGDONG_CITIES = {
    "广州":   (23.13, 113.26),
    "深圳":   (22.54, 114.06),
    "珠海":   (22.27, 113.58),
    "汕头":   (23.35, 116.68),
    "佛山":   (23.02, 113.12),
    "韶关":   (24.81, 113.60),
    "湛江":   (21.27, 110.36),
    "肇庆":   (23.05, 112.47),
    "江门":   (22.58, 113.08),
    "茂名":   (21.66, 110.93),
    "惠州":   (23.11, 114.42),
    "梅州":   (24.29, 116.12),
    "汕尾":   (22.77, 115.38),
    "河源":   (23.74, 114.70),
    "阳江":   (21.86, 111.98),
    "清远":   (23.68, 113.06),
    "东莞":   (23.04, 113.75),
    "中山":   (22.52, 113.39),
    "潮州":   (23.66, 116.62),
    "揭阳":   (23.55, 116.37),
    "云浮":   (22.92, 112.04),
}

# ── 全国主要城市坐标 ──
NATIONAL_CITIES = {
    "北京": (39.90, 116.40), "上海": (31.23, 121.47), "天津": (39.13, 117.20),
    "重庆": (29.56, 106.55), "成都": (30.57, 104.07), "武汉": (30.58, 114.27),
    "杭州": (30.27, 120.15), "西安": (34.26, 108.94), "南京": (32.06, 118.80),
    "长沙": (28.23, 112.94), "郑州": (34.75, 113.65), "沈阳": (41.80, 123.43),
    "哈尔滨": (45.75, 126.65), "昆明": (25.04, 102.68), "贵阳": (26.65, 106.63),
    "福州": (26.07, 119.30), "厦门": (24.48, 118.09), "济南": (36.67, 116.98),
    "青岛": (36.07, 120.38), "大连": (38.91, 121.60), "石家庄": (38.04, 114.51),
    "太原": (37.87, 112.55), "兰州": (36.06, 103.83), "乌鲁木齐": (43.83, 87.62),
    "呼和浩特": (40.84, 111.75), "拉萨": (29.65, 91.13), "南宁": (22.82, 108.37),
    "海口": (20.04, 110.35), "银川": (38.49, 106.23), "西宁": (36.62, 101.78),
    "合肥": (31.82, 117.23), "南昌": (28.68, 115.86),
}

# 合并
ALL_CITIES = {**NATIONAL_CITIES, **GUANGDONG_CITIES}


def _fetch_open_meteo(lat: float, lon: float, timeout: int = 15) -> dict | None:
    """调用 Open-Meteo API 获取逐小时数据"""
    url = OPEN_METEO_URL.format(lat=lat, lon=lon)
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "EmpireBot/2.9.6"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read())
    except Exception as e:
        log.warning(f"Open-Meteo 请求失败 ({lat},{lon}): {e}")
        return None


def _parse_hourly(data: dict) -> list[dict]:
    """解析 Open-Meteo hourly 数据"""
    hourly = data.get("hourly", {})
    times = hourly.get("time", [])
    precip = hourly.get("precipitation", [])
    prob = hourly.get("precipitation_probability", [])
    temp = hourly.get("temperature_2m", [])
    humidity = hourly.get("relative_humidity_2m", [])
    wind = hourly.get("wind_speed_10m", [])

    rows = []
    for i in range(len(times)):
        rows.append({
            "time": times[i],
            "precipitation_mm": precip[i] if i < len(precip) else 0,
            "precipitation_prob": prob[i] if i < len(prob) else None,
            "temperature_c": temp[i] if i < len(temp) else None,
            "humidity": humidity[i] if i < len(humidity) else None,
            "wind_speed_kmh": wind[i] if i < len(wind) else None,
        })
    return rows


def fetch_city_precipitation(city: str, timeout: int = 15) -> dict | None:
    """获取单城市过去24h + 未来6h 逐小时降雨量（mm）"""
    coords = ALL_CITIES.get(city)
    if not coords:
        log.warning(f"未知城市坐标: {city}")
        return None

    lat, lon = coords
    raw = _fetch_open_meteo(lat, lon, timeout)
    if not raw:
        return None

    hourly = _parse_hourly(raw)
    if not hourly:
        return None

    # 分割：过去24h vs 未来6h
    now = datetime.now(timezone(timedelta(hours=8)))
    now_str = now.strftime("%Y-%m-%dT%H:00")

    past_24h = []
    future_6h = []
    for h in hourly:
        if h["time"] <= now_str:
            past_24h.append(h)
        else:
            future_6h.append(h)

    # 只保留最近24h
    past_24h = past_24h[-24:]

    def summarize(hours: list[dict]) -> dict:
        total_mm = sum(h["precipitation_mm"] for h in hours)
        max_mm = max((h["precipitation_mm"] for h in hours), default=0)
        max_hour = ""
        for h in hours:
            if h["precipitation_mm"] == max_mm:
                max_hour = h["time"]
        avg_prob = None
        probs = [h["precipitation_prob"] for h in hours if h["precipitation_prob"] is not None]
        if probs:
            avg_prob = round(sum(probs) / len(probs))
        return {
            "total_mm": round(total_mm, 1),
            "max_mm": round(max_mm, 1),
            "max_hour": max_hour,
            "avg_prob": avg_prob,
            "hours": hours,
        }

    return {
        "city": city,
        "past_24h": summarize(past_24h),
        "future_6h": summarize(future_6h),
        "current": hourly[-1] if hourly else {},
    }


def fetch_guangdong_precipitation() -> str:
    """获取广东省21市过去24h + 未来6h 降雨量，返回结构化报告文本"""
    results = []
    for city in GUANGDONG_CITIES:
        d = fetch_city_precipitation(city)
        if d:
            p24 = d["past_24h"]
            f6 = d["future_6h"]
            results.append({
                "city": city,
                "past_24h_total": p24["total_mm"],
                "past_24h_max": p24["max_mm"],
                "future_6h_total": f6["total_mm"],
                "future_6h_prob": f6["avg_prob"],
                "current_temp": d["current"].get("temperature_c"),
            })

    if not results:
        return "广东省降雨数据获取失败"

    # 按过去24h降雨量排序
    results.sort(key=lambda x: x["past_24h_total"], reverse=True)

    lines = [
        "【广东省21市降雨量精确数据】",
        f"数据时间: {datetime.now(timezone(timedelta(hours=8))).strftime('%Y-%m-%d %H:%M')}",
        f"数据源: Open-Meteo API (逐小时, 毫米级)",
        "",
        "=== 过去24小时累计降雨量 (mm) ===",
        f"{'城市':<6} {'24h累计':>8} {'最大时雨':>8} {'未来6h':>8} {'降雨概率':>6} {'当前温度':>6}",
        "─" * 52,
    ]
    for r in results:
        level = ""
        if r["past_24h_total"] >= 250:
            level = "🔴特大暴雨"
        elif r["past_24h_total"] >= 100:
            level = "🟠大暴雨"
        elif r["past_24h_total"] >= 50:
            level = "🟡暴雨"
        elif r["past_24h_total"] >= 25:
            level = "🔵大雨"
        elif r["past_24h_total"] >= 10:
            level = "中雨"
        else:
            level = "小雨"
        lines.append(
            f"{r['city']:<6} {r['past_24h_total']:>7.1f}mm {r['past_24h_max']:>7.1f}mm "
            f"{r['future_6h_total']:>7.1f}mm {r['future_6h_prob'] or 0:>5}% "
            f"{r['current_temp'] or '?':>5}℃ {level}"
        )

    # 汇总
    total_avg = sum(r["past_24h_total"] for r in results) / len(results)
    max_city = results[0]
    lines.extend([
        "",
        f"全省平均: {total_avg:.1f}mm",
        f"最大降雨: {max_city['city']} {max_city['past_24h_total']}mm",
        f"特大暴雨: {sum(1 for r in results if r['past_24h_total'] >= 250)}市",
        f"大暴雨:   {sum(1 for r in results if 100 <= r['past_24h_total'] < 250)}市",
        f"暴雨:     {sum(1 for r in results if 50 <= r['past_24h_total'] < 100)}市",
    ])

    return "\n".join(lines)


def fetch_city_weather(city: str, timeout: int = 10) -> dict | None:
    """获取单个城市天气（兼容旧接口）"""
    coords = ALL_CITIES.get(city)
    if not coords:
        return None

    lat, lon = coords
    raw = _fetch_open_meteo(lat, lon, timeout)
    if not raw:
        return None

    hourly = _parse_hourly(raw)
    if not hourly:
        return None

    now = datetime.now(timezone(timedelta(hours=8)))
    now_str = now.strftime("%Y-%m-%dT%H:00")

    # 当前
    current = hourly[-1] if hourly else {}

    # 过去24h
    past = [h for h in hourly if h["time"] <= now_str][-24:]
    past_precip_total = sum(h["precipitation_mm"] for h in past)

    # 未来6h
    future = [h for h in hourly if h["time"] > now_str][:6]
    future_precip_total = sum(h["precipitation_mm"] for h in future)
    future_prob = None
    probs = [h["precipitation_prob"] for h in future if h["precipitation_prob"] is not None]
    if probs:
        future_prob = round(sum(probs) / len(probs))

    return {
        "city": city,
        "current": {
            "temp": current.get("temperature_c", ""),
            "weather": _describe_precip(past_precip_total),
            "humidity": current.get("humidity", ""),
        },
        "tomorrow": {
            "weather_desc": _describe_precip(future_precip_total),
            "rain_prob": future_prob or 0,
            "temp_low": min((h["temperature_c"] for h in future if h["temperature_c"] is not None), default=""),
            "temp_high": max((h["temperature_c"] for h in future if h["temperature_c"] is not None), default=""),
            "precip_mm": round(future_precip_total, 1),
        },
        "past_24h_mm": round(past_precip_total, 1),
    }


def _describe_precip(mm: float) -> str:
    """根据降水量(mm)描述雨量等级"""
    if mm >= 250:
        return "特大暴雨"
    elif mm >= 100:
        return "大暴雨"
    elif mm >= 50:
        return "暴雨"
    elif mm >= 25:
        return "大雨"
    elif mm >= 10:
        return "中雨"
    elif mm >= 1:
        return "小雨"
    else:
        return "无降水"


def fetch_all_weather(cities: list[str] | None = None, target: str = "tomorrow") -> str:
    """批量获取天气，返回结构化文本（兼容旧接口）"""
    cities = cities or list(NATIONAL_CITIES.keys())
    results = []
    for city in cities:
        w = fetch_city_weather(city)
        if w:
            day = w.get(target, {})
            if day:
                results.append(
                    f"{city}: {day.get('weather_desc','')} "
                    f"温度{day.get('temp_low','?')}~{day.get('temp_high','?')}℃ "
                    f"降雨概率{day.get('rain_prob','?')}% "
                    f"降雨量{day.get('precip_mm', '?')}mm"
                )
    return "\n".join(results) if results else "天气数据获取失败"
