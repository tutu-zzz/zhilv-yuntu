<script setup lang="ts">
import { ref } from "vue";

import {
  formatShortDate,
  useItinerary,
} from "../../composables/useItinerary";
import type { Itinerary } from "../../types";

const props = defineProps<{
  itinerary: Itinerary | null;
  selectedDay: number;
}>();

const emit = defineEmits<{
  selectDay: [dayIndex: number];
}>();

const failedImageKeys = ref(new Set<string>());

const { dayBudgetItems, mapPoints } = useItinerary(
  () => props.itinerary,
  () => null
);

function markImageAsFailed(pointKey: string) {
  failedImageKeys.value = new Set([...failedImageKeys.value, pointKey]);
}
</script>

<template>
  <div class="itinerary-panel">
    <!-- 选天提示 -->
    <div class="ws-card itinerary-hint">
      <div class="ws-card__header">行程调整</div>
      <p class="itinerary-hint__text">
        点击某一天卡片将其选中，然后在右侧 AI 助手输入想如何调整这一天。
      </p>
      <div v-if="itinerary" class="itinerary-hint__scope">
        当前选中：<strong>第 {{ selectedDay }} 天</strong>
        <span v-if="itinerary.days.find((d) => d.day_index === selectedDay)?.theme">
          · {{ itinerary.days.find((d) => d.day_index === selectedDay)?.theme }}
        </span>
      </div>
    </div>

    <!-- 每日行程 -->
    <div class="ws-card ws-card--full">
      <div class="ws-card__header">每日行程</div>
      <div v-if="itinerary" class="itinerary-day-list">
        <template v-for="day in itinerary.days" :key="day.day_index">
          <details
            :class="['itinerary-day', { 'itinerary-day--selected': selectedDay === day.day_index }]"
            @toggle="$event.preventDefault()"
          >
            <summary
              class="itinerary-day__head"
              @click="emit('selectDay', day.day_index); $event.stopPropagation()"
            >
              <span>第{{ day.day_index }}天 · {{ day.theme || "" }}</span>
              <span class="ws-muted">{{ formatShortDate(day.date) }}</span>
            </summary>
            <div class="itinerary-day__body">
            <div>
              <span class="ws-muted">主要景点：</span>{{ day.spots[0]?.name || "未安排" }}
            </div>
            <div>
              <span class="ws-muted">景点地址：</span>{{ day.spots[0]?.address || day.spots[0]?.location || "待补充" }}
            </div>
            <div>
              <span class="ws-muted">餐饮建议：</span>{{ day.meals[0]?.name || "未安排" }}
            </div>
            <div>
              <span class="ws-muted">餐饮地址：</span>{{ day.meals[0]?.address || "待补充" }}
            </div>
            <div>
              <span class="ws-muted">住宿安排：</span>{{ day.hotel?.name || "未安排" }}
            </div>
            <div>
              <span class="ws-muted">住宿地址：</span>{{ day.hotel?.address || day.hotel?.location || "待补充" }}
            </div>
            <div>
              <span class="ws-muted">交通信息：</span>
              {{ day.transport[0]?.distance_km != null ? `${day.transport[0].distance_km.toFixed(2)} km / ${day.transport[0].estimated_minutes ?? 0} 分钟` : day.transport[0]?.duration || "待补充" }}
            </div>
            <div>
              <span class="ws-muted">备注：</span>{{ day.notes[day.notes.length - 1] || "无" }}
            </div>
          </div>
        </details>
        </template>
      </div>
      <div v-else class="ws-empty">暂无行程</div>
    </div>

    <!-- 按天花费 -->
    <div class="ws-card ws-card--full">
      <div class="ws-card__header">按天花费</div>
      <div class="ws-day-budget-grid">
        <div v-for="item in dayBudgetItems" :key="item.key" class="ws-day-budget">
          <div class="ws-day-budget__head">
            <span>{{ item.title }}</span>
            <span>{{ item.subtitle }}</span>
          </div>
          <div class="ws-day-budget__body">
            <div class="ws-row-between"><span>门票</span><span>¥{{ item.tickets.toFixed(0) }}</span></div>
            <div class="ws-row-between"><span>餐饮</span><span>¥{{ item.meals.toFixed(0) }}</span></div>
            <div class="ws-row-between"><span>交通</span><span>¥{{ item.transport.toFixed(0) }}</span></div>
            <div class="ws-row-between"><span>住宿</span><span>¥{{ item.hotel.toFixed(0) }}</span></div>
            <div class="ws-row-between ws-row-between--bold">
              <span>当日合计</span><span>¥{{ item.total.toFixed(0) }}</span>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- 点位明细 -->
    <div class="ws-card ws-card--full">
      <div class="ws-card__header">地图点位明细</div>
      <div class="ws-point-grid">
        <div v-for="point in mapPoints" :key="point.key" class="ws-point">
          <div class="ws-point__head">
            <span>第{{ point.dayIndex }}天 · {{ point.name }}</span>
            <span>{{ formatShortDate(point.date) }}</span>
          </div>
          <img
            v-if="point.imageUrl && !failedImageKeys.has(point.key)"
            class="ws-point__img"
            :src="point.imageUrl"
            :alt="`${point.name} 图片`"
            @error="markImageAsFailed(point.key)"
          />
          <div v-else class="ws-point__img ws-point__img--empty">暂无图片</div>
          <div class="ws-point__info"><span class="ws-muted">主题：</span>{{ point.theme }}</div>
          <div class="ws-point__info"><span class="ws-muted">地址：</span>{{ point.address }}</div>
          <div class="ws-point__desc">{{ point.description }}</div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.itinerary-panel {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 12px;
  align-items: start;
}

.itinerary-hint__text {
  margin: 0 0 8px;
  font-size: 14px;
  color: #636366;
  line-height: 1.6;
}

.itinerary-hint__scope {
  font-size: 14px;
  color: #3c3c43;
}

.itinerary-day-list {
  display: grid;
  gap: 8px;
}

.itinerary-day {
  border-radius: 10px;
  border: 1.5px solid rgba(0, 0, 0, 0.08);
  overflow: hidden;
  cursor: pointer;
  transition: border-color 0.2s ease, box-shadow 0.2s ease;
}

.itinerary-day:hover {
  border-color: rgba(0, 122, 255, 0.4);
}

.itinerary-day--selected {
  border-color: #007aff;
  box-shadow: 0 0 0 2px rgba(0, 122, 255, 0.15);
}

.itinerary-day__head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 14px;
  background: #f2f2f7;
  font-size: 14px;
  font-weight: 600;
  color: #1c1c1e;
  list-style: none;
  cursor: pointer;
}

.itinerary-day__head::-webkit-details-marker {
  display: none;
}

.itinerary-day__head::after {
  content: "▸";
  font-size: 14px;
  font-weight: 700;
  color: #007aff;
  transition: transform 0.3s ease;
}

.itinerary-day[open] .itinerary-day__head::after {
  transform: rotate(90deg);
}

.itinerary-day__body {
  display: grid;
  gap: 8px;
  padding: 14px;
  font-size: 14px;
  color: #3c3c43;
  line-height: 1.7;
  border-top: 0.5px solid rgba(0, 0, 0, 0.06);
}

.itinerary-day[open] .itinerary-day__body {
  border-top: 0.5px solid rgba(0, 0, 0, 0.06);
}
</style>
