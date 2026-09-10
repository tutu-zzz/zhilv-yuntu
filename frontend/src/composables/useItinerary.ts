import { computed } from "vue";

import type { Itinerary, WeatherForecastResponse } from "../types";

/** 与 AmapTripMap.vue 内部 TripMapPoint 结构一致的共享地图点类型 */
export interface TripMapPoint {
  key: string;
  dayIndex: number;
  date: string;
  theme: string;
  name: string;
  address: string;
  latitude: number | null | undefined;
  longitude: number | null | undefined;
  poiId: string | null | undefined;
  imageUrl?: string | null;
  description: string;
}

const technicalTipKeywords = [
  "LLM",
  "RAG",
  "LangChain",
  "Chroma",
  "演示",
  "测试",
  "规则",
  "模型",
  "源码",
];
const rainWeatherKeywords = ["雨", "阵雨", "雷阵雨", "小雨", "中雨", "大雨"];
const sunnyTipKeywords = ["防晒", "太阳", "日照", "晒"];

export function formatShortDate(dateText?: string | null): string {
  if (!dateText) return "待定";
  const parts = dateText.split("-");
  return parts.length !== 3 ? dateText : `${parts[1]}-${parts[2]}`;
}

export function formatWeatherDate(
  dateText?: string | null,
  week?: string | null
): string {
  const weekdayMap: Record<string, string> = {
    "1": "周一",
    "2": "周二",
    "3": "周三",
    "4": "周四",
    "5": "周五",
    "6": "周六",
    "7": "周日",
  };
  const weekday = week ? weekdayMap[week] || `周${week}` : "";
  return [formatShortDate(dateText), weekday].filter(Boolean).join(" ");
}

/**
 * 从 Itinerary 派生工作台各面板需要的展示数据。
 * 参数为 getter 函数，面板/工作台可传 () => props.itinerary。
 */
export function useItinerary(
  itinerary: () => Itinerary | null,
  weather: () => WeatherForecastResponse | null
) {
  const budgetItems = computed(() => {
    const it = itinerary();
    if (!it) return [];
    const b = it.budget_breakdown;
    return [
      { label: "景点门票", value: `¥${b.tickets.toFixed(0)}` },
      { label: "酒店住宿", value: `¥${b.hotel.toFixed(0)}` },
      { label: "餐饮费用", value: `¥${b.meals.toFixed(0)}` },
      { label: "交通费用", value: `¥${b.transport.toFixed(0)}` },
    ];
  });

  const dayBudgetItems = computed(() => {
    const it = itinerary();
    if (!it) return [];
    return it.days.map((day) => {
      const tickets = day.spots.reduce(
        (s, sp) => s + (sp.estimated_cost ?? 0),
        0
      );
      const meals = day.meals.reduce((s, m) => s + (m.estimated_cost ?? 0), 0);
      const transport = day.transport.reduce(
        (s, t) => s + (t.estimated_cost ?? 0),
        0
      );
      const hotel = day.hotel?.estimated_cost ?? 0;
      return {
        key: day.day_index,
        title: `第${day.day_index}天`,
        subtitle: day.theme || "",
        tickets,
        meals,
        transport,
        hotel,
        total: tickets + meals + transport + hotel,
      };
    });
  });

  const mapPoints = computed<TripMapPoint[]>(() => {
    const it = itinerary();
    if (!it) return [];
    return it.days.flatMap((day) =>
      day.spots.map((spot) => ({
        key: `${day.day_index}-${spot.name}`,
        dayIndex: day.day_index,
        date: day.date || "待定",
        theme: day.theme || "",
        name: spot.name,
        address: spot.address || spot.location || "待补充",
        latitude: spot.latitude,
        longitude: spot.longitude,
        poiId: spot.poi_id,
        imageUrl: spot.image_url,
        description: spot.description || "暂无说明",
      }))
    );
  });

  const weatherText = computed(() => {
    const w = weather();
    if (!w) return "";
    return w.days
      .map((d) => `${d.day_weather || ""}${d.night_weather || ""}`)
      .join(" ");
  });

  const hasRainyWeather = computed(() =>
    rainWeatherKeywords.some((k) => weatherText.value.includes(k))
  );

  const displayTips = computed(() => {
    const it = itinerary();
    if (!it) return [];
    const tips = it.tips
      .map((t) => t.trim())
      .filter(Boolean)
      .filter((t) => !technicalTipKeywords.some((k) => t.includes(k)));
    const weatherAware = hasRainyWeather.value
      ? tips.filter((t) => !sunnyTipKeywords.some((k) => t.includes(k)))
      : tips;
    if (hasRainyWeather.value) {
      weatherAware.push("天气可能有雨，建议随身带伞或轻便雨衣。");
      weatherAware.push("阴雨天路面湿滑，建议穿防滑鞋。");
    }
    return Array.from(new Set(weatherAware));
  });

  return { budgetItems, dayBudgetItems, mapPoints, displayTips, hasRainyWeather };
}
