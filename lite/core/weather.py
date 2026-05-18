"""天气数据工具 — 基于 wttr.in（免费，无需 API Key）"""
import urllib.request
import json
import re
from core.logger import get_logger

log = get_logger("weather")

WTTR_URL = "https://wttr.in/{city}?format=j1"
CITIES = [
    "北京", "上海", "广州", "深圳", "成都", "重庆", "武汉", "杭州",
    "西安", "南京", "天津", "郑州", "长沙", "沈阳", "哈尔滨",
    "昆明", "贵阳", "福州", "厦门", "济南", "青岛", "大连",
    "石家庄", "太原", "兰州", "乌鲁木齐", "呼和浩特", "拉萨",
    "南宁", "海口", "银川", "西宁", "合肥", "南昌",
]


def fetch_city_weather(city: str, timeout: int = 10) -> dict | None:
    """获取单个城市天气"""
    try:
        url = WTTR_URL.format(city=urllib.request.quote(city))
        req = urllib.request.Request(url, headers={"User-Agent": "EmpireBot/2.9"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read())

        current = data.get("current_condition", [{}])[0]
        forecast = data.get("weather", [])

        # 明天 = forecast[1]，大后天 = forecast[2]
        tomorrow = forecast[1] if len(forecast) > 1 else {}
        day_after = forecast[2] if len(forecast) > 2 else {}

        def parse_day(day_data: dict) -> dict:
            if not day_data:
                return {}
            hourly = day_data.get("hourly", [])
            # 中午时段 (12:00) 作为白天代表
            noon = hourly[4] if len(hourly) > 4 else (hourly[0] if hourly else {})
            return {
                "date": day_data.get("date", ""),
                "temp_high": day_data.get("maxtempC", ""),
                "temp_low": day_data.get("mintempC", ""),
                "weather_desc": noon.get("lang_zh", [{}])[0].get("value", noon.get("weatherDesc", [{}])[0].get("value", "")),
                "wind_dir": noon.get("winddir16Point", ""),
                "wind_speed": noon.get("windspeedKmph", ""),
                "rain_prob": noon.get("chanceofrain", ""),
                "humidity": noon.get("humidity", ""),
            }

        return {
            "city": city,
            "current": {
                "temp": current.get("temp_C", ""),
                "weather": current.get("lang_zh", [{}])[0].get("value", ""),
                "humidity": current.get("humidity", ""),
            },
            "tomorrow": parse_day(tomorrow),
            "day_after": parse_day(day_after),
        }
    except Exception as e:
        log.warning(f"获取 {city} 天气失败: {e}")
        return None


def fetch_all_weather(cities: list[str] | None = None, target: str = "tomorrow") -> str:
    """批量获取天气，返回结构化文本"""
    cities = cities or CITIES
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
                    f"风向{day.get('wind_dir','')} 风速{day.get('wind_speed','?')}km/h"
                )
    return "\n".join(results) if results else "天气数据获取失败"
