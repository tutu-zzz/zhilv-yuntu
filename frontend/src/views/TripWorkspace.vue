<script setup lang="ts">
import { computed, ref, watch, onMounted } from "vue";
import { message } from "ant-design-vue";
import {
  saveTrip,
  fetchWeatherForecast,
  getMarkdownExportUrl,
  getPdfExportUrl,
} from "../services/api";
import { formatShortDate, useItinerary } from "../composables/useItinerary";
import TripNav from "../components/workspace/TripNav.vue";
import AiAssistantPanel from "../components/workspace/AiAssistantPanel.vue";
import OverviewPanel from "../components/workspace/OverviewPanel.vue";
import ItineraryPanel from "../components/workspace/ItineraryPanel.vue";
import PlacesPanel from "../components/workspace/PlacesPanel.vue";
import NotesPanel from "../components/workspace/NotesPanel.vue";
import type { Itinerary, WeatherForecastResponse } from "../types";

const props = defineProps<{
  itinerary: Itinerary | null;
}>();

const emit = defineEmits<{
  backHome: [];
  viewHistory: [];
  updated: [itinerary: Itinerary];
}>();

const activePanel = ref<string>("overview");
const selectedDay = ref<number>(props.itinerary?.days[0]?.day_index || 1);
const aiCollapsed = ref<boolean>(false);

const saving = ref(false);
const exportingPdf = ref(false);
const exportingMarkdown = ref(false);

const weather = ref<WeatherForecastResponse | null>(null);
const weatherLoading = ref(false);
const weatherError = ref("");

const { mapPoints, displayTips } = useItinerary(() => props.itinerary, () => weather.value);

const firstDayBudget = computed(() => {
  if (!props.itinerary || props.itinerary.days.length === 0) return 0;
  const day = props.itinerary.days[0];
  const tickets = day.spots.reduce((s, sp) => s + (sp.estimated_cost ?? 0), 0);
  const meals = day.meals.reduce((s, m) => s + (m.estimated_cost ?? 0), 0);
  const transport = day.transport.reduce((s, t) => s + (t.estimated_cost ?? 0), 0);
  const hotel = day.hotel?.estimated_cost ?? 0;
  return tickets + meals + transport + hotel;
});

async function loadWeather() {
  if (!props.itinerary?.destination) {
    weather.value = null;
    return;
  }
  weatherLoading.value = true;
  weatherError.value = "";
  try {
    weather.value = await fetchWeatherForecast(props.itinerary.destination);
  } catch {
    weather.value = null;
    weatherError.value = "天气信息加载失败。";
    message.warning("天气信息加载失败。");
  } finally {
    weatherLoading.value = false;
  }
}

async function handleSave() {
  if (!props.itinerary || saving.value) return;
  saving.value = true;
  try {
    await saveTrip(props.itinerary);
    message.success("行程已保存。");
  } catch {
    message.error("保存行程失败。");
  } finally {
    saving.value = false;
  }
}

async function handleExportPdf() {
  if (!props.itinerary || exportingPdf.value) return;
  const w = window.open("about:blank", "_blank");
  exportingPdf.value = true;
  try {
    await saveTrip(props.itinerary);
    if (w) w.location.href = getPdfExportUrl(props.itinerary.trip_id);
  } catch {
    w?.close();
    message.error("导出 PDF 前同步当前行程失败。");
  } finally {
    exportingPdf.value = false;
  }
}

async function handleExportMarkdown() {
  if (!props.itinerary || exportingMarkdown.value) return;
  const w = window.open("about:blank", "_blank");
  exportingMarkdown.value = true;
  try {
    await saveTrip(props.itinerary);
    if (w) w.location.href = getMarkdownExportUrl(props.itinerary.trip_id);
  } catch {
    w?.close();
    message.error("导出 Markdown 前同步当前行程失败。");
  } finally {
    exportingMarkdown.value = false;
  }
}

watch(() => props.itinerary?.destination, () => {
  void loadWeather();
});

watch(() => props.itinerary?.trip_id, () => {
  const firstDay = props.itinerary?.days[0];
  if (firstDay) {
    selectedDay.value = firstDay.day_index;
  }
});

watch(selectedDay, (newDay) => {
  if (activePanel.value !== "itinerary") {
    activePanel.value = "itinerary";
  }
});

onMounted(() => {
  if (props.itinerary?.destination) {
    void loadWeather();
  }
  selectedDay.value = props.itinerary?.days[0]?.day_index || 1;
});
</script>

<template>
  <div v-if="itinerary" class="trip-workspace" :class="{ 'trip-workspace--ai-collapsed': aiCollapsed }">
    <!-- 左栏导航 -->
    <TripNav
      :itinerary="itinerary"
      :active-panel="activePanel"
      :saving="saving"
      :exporting-pdf="exportingPdf"
      :exporting-markdown="exportingMarkdown"
      @navigate="activePanel = $event"
      @back-home="$emit('backHome')"
      @view-history="$emit('viewHistory')"
      @save="handleSave"
      @export-pdf="handleExportPdf"
      @export-markdown="handleExportMarkdown"
    />

    <!-- 中栏内容 -->
    <div class="workspace-content">
      <!-- 总览 -->
      <OverviewPanel
        v-if="activePanel === 'overview'"
        :itinerary="itinerary"
        :weather="weather"
        :weather-loading="weatherLoading"
        :weather-error="weatherError"
      />

      <!-- 行程 -->
      <ItineraryPanel
        v-if="activePanel === 'itinerary'"
        :itinerary="itinerary"
        :selected-day="selectedDay"
        @select-day="selectedDay = $event"
      />

      <!-- 地点 -->
      <PlacesPanel
        v-if="activePanel === 'places'"
        :itinerary="itinerary"
      />

      <!-- 笔记 -->
      <NotesPanel
        v-if="activePanel === 'notes'"
        :itinerary="itinerary"
      />
    </div>

    <!-- 右栏 AI 助手（可收起为竖条） -->
    <AiAssistantPanel
      :itinerary="itinerary"
      :selected-day="selectedDay"
      :collapsed="aiCollapsed"
      @toggle="aiCollapsed = !aiCollapsed"
      @updated="$emit('updated', $event)"
    />
  </div>

  <div v-else class="trip-workspace-empty">
    <div class="ws-card ws-empty">
      <h2>暂无行程</h2>
      <p>先回到规划页生成一个行程，然后在这里继续完善</p>
      <button class="ws-btn ws-btn--primary" @click="$emit('backHome')">
        返回规划页
      </button>
    </div>
  </div>
</template>

<style scoped>
@import "../assets/workspace.css";

.trip-workspace {
  display: grid;
  grid-template-columns: 240px 1fr 360px;
  gap: 16px;
  min-height: calc(100vh - 72px);
  transition: grid-template-columns 0.3s ease;
}

/* AI 助手收起时右栏空间完全归还中栏（入口为右上角悬浮按钮） */
.trip-workspace--ai-collapsed {
  grid-template-columns: 240px 1fr;
}

.workspace-content {
  display: grid;
  gap: 12px;
  align-items: start;
}

.trip-workspace-empty {
  display: grid;
  place-items: center;
  min-height: calc(100vh - 72px);
}

/* 预算明细紧凑样式 */
.budget-card-compact {
  padding: 14px;
}

.budget-card-compact .ws-card__header {
  margin-bottom: 10px;
  padding-bottom: 6px;
}

.budget-card-compact .ws-budget-grid {
  gap: 6px;
}

.budget-card-compact .ws-budget-item {
  padding: 8px 10px;
}

.budget-card-compact .ws-budget-total {
  margin-top: 8px;
  padding: 10px 12px;
}

.budget-card-compact .ws-budget-total strong {
  font-size: 20px;
}

/* 全屏地图样式 */
.full-width-map {
  grid-column: 1 / -1;
  min-height: 400px;
}

@media (max-width: 1280px) {
  .trip-workspace {
    grid-template-columns: 220px 1fr 320px;
  }

  .trip-workspace--ai-collapsed {
    grid-template-columns: 220px 1fr;
  }
}

@media (max-width: 960px) {
  .trip-workspace,
  .trip-workspace--ai-collapsed {
    grid-template-columns: 1fr;
  }
}
</style>