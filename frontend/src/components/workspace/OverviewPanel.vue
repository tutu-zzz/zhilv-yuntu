<script setup lang="ts">
import AmapTripMap from "../AmapTripMap.vue";
import {
  formatShortDate,
  formatWeatherDate,
  useItinerary,
} from "../../composables/useItinerary";
import type { Itinerary, WeatherForecastResponse } from "../../types";

const props = defineProps<{
  itinerary: Itinerary | null;
  weather: WeatherForecastResponse | null;
  weatherLoading: boolean;
  weatherError: string;
}>();

const { budgetItems, mapPoints, displayTips } = useItinerary(
  () => props.itinerary,
  () => props.weather
);
</script>

<template>
  <div class="overview-panel">
    <!-- 概览 -->
    <div class="ws-card">
      <h2 class="ws-card__title">{{ itinerary?.destination }}旅行计划</h2>
      <div class="ws-info">
        <span class="ws-info__label">行程 ID</span>
        <span>{{ itinerary?.trip_id }}</span>
      </div>
      <div class="ws-info">
        <span class="ws-info__label">日期</span>
        <span v-if="itinerary?.days?.length">
          {{ formatShortDate(itinerary.days[0]?.date) }} 至
          {{ formatShortDate(itinerary.days[itinerary.days.length - 1]?.date) }}
        </span>
        <span v-else>待定</span>
      </div>
      <p class="ws-summary">{{ itinerary?.summary }}</p>
      <div v-if="displayTips.length" class="ws-tips">
        <div class="ws-tips__title">旅行提示</div>
        <ul>
          <li v-for="tip in displayTips" :key="tip">{{ tip }}</li>
        </ul>
      </div>
    </div>

    <!-- 预算 -->
    <div class="ws-card budget-card-compact">
      <div class="ws-card__header">预算明细</div>
      <div class="ws-budget-grid">
        <div v-for="item in budgetItems" :key="item.label" class="ws-budget-item">
          <span class="ws-budget-item__label">{{ item.label }}</span>
          <span class="ws-budget-item__value">{{ item.value }}</span>
        </div>
      </div>
      <div class="ws-budget-total">
        <span>预估总费用</span>
        <strong>¥{{ itinerary?.estimated_budget.toFixed(0) }}</strong>
      </div>
    </div>

    <!-- 天气 -->
    <div class="ws-card">
      <div class="ws-card__header">天气信息</div>
      <div v-if="weatherLoading" class="ws-empty">正在加载...</div>
      <div v-else-if="weatherError" class="ws-empty">{{ weatherError }}</div>
      <div v-else-if="weather" class="ws-weather-grid">
        <div v-for="day in weather.days" :key="`${day.date}-${day.week}`" class="ws-weather-item">
          <div class="ws-weather-item__date">{{ formatWeatherDate(day.date, day.week) }}</div>
          <div class="ws-weather-item__temp">{{ day.day_temp || "-" }}° / {{ day.night_temp || "-" }}°</div>
          <div class="ws-weather-item__desc">{{ day.day_weather || "未知" }} / {{ day.night_weather || "未知" }}</div>
        </div>
      </div>
      <div v-else class="ws-empty">暂无天气信息</div>
    </div>

    <!-- 地图 -->
    <div class="ws-card ws-card--map overview-map full-width-map">
      <div class="ws-card__header">景点地图</div>
      <AmapTripMap :points="mapPoints" />
    </div>
  </div>
</template>

<style scoped>
.overview-panel {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 12px;
  align-items: start;
}

.overview-map {
  grid-column: 1 / -1;
  min-height: 400px;
}
</style>
