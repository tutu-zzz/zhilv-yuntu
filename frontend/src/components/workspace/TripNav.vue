<script setup lang="ts">
import { computed } from "vue";

import { formatShortDate } from "../../composables/useItinerary";
import type { Itinerary } from "../../types";

const props = defineProps<{
  itinerary: Itinerary | null;
  activePanel: string;
  saving: boolean;
  exportingPdf: boolean;
  exportingMarkdown: boolean;
}>();

const emit = defineEmits<{
  navigate: [panel: string];
  backHome: [];
  viewHistory: [];
  save: [];
  exportPdf: [];
  exportMarkdown: [];
}>();

const navItems = [
  { key: "overview", label: "总览" },
  { key: "itinerary", label: "行程" },
  { key: "places", label: "地点" },
  { key: "notes", label: "笔记" },
];

const dateRange = computed(() => {
  if (!props.itinerary || props.itinerary.days.length === 0) return "";
  const first = props.itinerary.days[0]?.date;
  const last = props.itinerary.days[props.itinerary.days.length - 1]?.date;
  return `${formatShortDate(first)} — ${formatShortDate(last)}`;
});

const dayCount = computed(() => props.itinerary?.days.length ?? 0);
</script>

<template>
  <aside class="trip-nav">
    <div class="trip-nav__top">
      <button class="trip-nav__back ws-btn" @click="emit('backHome')">← 我的旅行</button>

      <div v-if="itinerary" class="trip-nav__trip">
        <div class="trip-nav__dest">{{ itinerary.destination }}</div>
        <div class="trip-nav__meta">{{ dateRange }}</div>
        <div class="trip-nav__meta">{{ dayCount }} 天</div>
      </div>
    </div>

    <nav class="trip-nav__list">
      <button
        v-for="item in navItems"
        :key="item.key"
        :class="['trip-nav__item', { 'trip-nav__item--active': activePanel === item.key }]"
        @click="emit('navigate', item.key)"
      >
        {{ item.label }}
      </button>
    </nav>

    <div class="trip-nav__bottom">
      <div class="trip-nav__label">操作</div>
      <button class="trip-nav__action ws-btn" :disabled="saving" @click="emit('save')">
        {{ saving ? "保存中..." : "保存行程" }}
      </button>
      <button class="trip-nav__action ws-btn" :disabled="exportingPdf" @click="emit('exportPdf')">
        {{ exportingPdf ? "准备中..." : "导出 PDF" }}
      </button>
      <button class="trip-nav__action ws-btn" :disabled="exportingMarkdown" @click="emit('exportMarkdown')">
        {{ exportingMarkdown ? "准备中..." : "导出 Markdown" }}
      </button>
      <button class="trip-nav__action ws-btn" @click="emit('viewHistory')">历史列表</button>
    </div>
  </aside>
</template>

<style scoped>
.trip-nav {
  position: sticky;
  top: 76px;
  align-self: start;
  display: flex;
  flex-direction: column;
  gap: 16px;
  padding: 16px;
  border-radius: 12px;
  background: #ffffff;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.08);
  height: calc(100vh - 96px);
  overflow-y: auto;
}

.trip-nav__top {
  display: grid;
  gap: 12px;
}

.trip-nav__back {
  padding: 0;
  color: #007aff;
  background: transparent;
  font-size: 14px;
  font-weight: 500;
}

.trip-nav__trip {
  display: grid;
  gap: 2px;
  padding: 10px 0;
  border-top: 0.5px solid rgba(0, 0, 0, 0.06);
  border-bottom: 0.5px solid rgba(0, 0, 0, 0.06);
}

.trip-nav__dest {
  font-size: 20px;
  font-weight: 700;
  color: #1c1c1e;
}

.trip-nav__meta {
  font-size: 12px;
  color: #8e8e93;
}

.trip-nav__list {
  display: grid;
  gap: 2px;
}

.trip-nav__item {
  border: none;
  border-radius: 8px;
  padding: 10px 12px;
  background: transparent;
  color: #3c3c43;
  font-size: 14px;
  font-weight: 500;
  text-align: left;
  cursor: pointer;
  transition: all 0.2s ease;
}

.trip-nav__item:hover {
  background: #f2f2f7;
}

.trip-nav__item--active {
  background: #eaf2ff;
  color: #007aff;
  font-weight: 600;
}

.trip-nav__bottom {
  display: grid;
  gap: 4px;
  margin-top: auto;
  padding-top: 12px;
  border-top: 0.5px solid rgba(0, 0, 0, 0.06);
}

.trip-nav__label {
  font-size: 12px;
  font-weight: 600;
  color: #8e8e93;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  padding: 4px 8px;
}

.trip-nav__action {
  width: 100%;
  text-align: left;
  background: transparent;
  color: #007aff;
  font-size: 14px;
  font-weight: 500;
  padding: 8px 12px;
}
</style>
