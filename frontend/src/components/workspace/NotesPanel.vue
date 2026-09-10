<script setup lang="ts">
import {
  formatShortDate,
  useItinerary,
} from "../../composables/useItinerary";
import type { Itinerary } from "../../types";

const props = defineProps<{
  itinerary: Itinerary | null;
}>();

const { displayTips } = useItinerary(() => props.itinerary, () => null);
</script>

<template>
  <div class="notes-panel">
    <!-- 行程摘要 -->
    <div v-if="itinerary" class="ws-card ws-card--full">
      <h2 class="ws-card__title">行程摘要</h2>
      <div class="ws-info">
        <span class="ws-info__label">目的地</span>
        <span>{{ itinerary.destination }}</span>
      </div>
      <div class="ws-info">
        <span class="ws-info__label">日期</span>
        <span v-if="itinerary.days.length">
          {{ formatShortDate(itinerary.days[0]?.date) }} 至
          {{ formatShortDate(itinerary.days[itinerary.days.length - 1]?.date) }}
        </span>
        <span v-else>待定</span>
      </div>
      <p class="ws-summary">{{ itinerary.summary }}</p>

      <div v-if="displayTips.length" class="ws-tips">
        <div class="ws-tips__title">旅行提示</div>
        <ul>
          <li v-for="tip in displayTips" :key="tip">{{ tip }}</li>
        </ul>
      </div>
    </div>

    <!-- 逐日备注 -->
    <div v-if="itinerary && itinerary.days.some((d) => d.notes.length)" class="ws-card ws-card--full">
      <div class="ws-card__header">每日备注</div>
      <div class="notes-day-list">
        <div
          v-for="day in itinerary.days"
          :key="day.day_index"
          class="notes-day"
        >
          <div class="notes-day__head">
            <span>第{{ day.day_index }}天 · {{ day.theme || "" }}</span>
            <span class="ws-muted">{{ formatShortDate(day.date) }}</span>
          </div>
          <div v-if="day.notes.length" class="notes-day__body">
            <div v-for="(note, i) in day.notes" :key="i" class="notes-day__item">
              {{ note }}
            </div>
          </div>
          <div v-else class="notes-day__body ws-muted">当天暂无备注</div>
        </div>
      </div>
    </div>

    <div v-else class="ws-card ws-card--full">
      <div class="ws-empty">该行程暂无笔记内容</div>
    </div>
  </div>
</template>

<style scoped>
.notes-panel {
  display: grid;
  gap: 12px;
}

.notes-day-list {
  display: grid;
  gap: 8px;
}

.notes-day {
  border-radius: 10px;
  border: 0.5px solid rgba(0, 0, 0, 0.06);
  overflow: hidden;
}

.notes-day__head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 14px;
  background: #f2f2f7;
  font-size: 14px;
  font-weight: 600;
  color: #1c1c1e;
}

.notes-day__body {
  display: grid;
  gap: 8px;
  padding: 14px;
  font-size: 14px;
  color: #3c3c43;
  line-height: 1.7;
  border-top: 0.5px solid rgba(0, 0, 0, 0.06);
}

.notes-day__item {
  padding-left: 12px;
  border-left: 2px solid #e5e5ea;
}
</style>
