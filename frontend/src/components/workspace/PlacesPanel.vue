<script setup lang="ts">
import { computed, ref } from "vue";

import type { Itinerary } from "../../types";

const props = defineProps<{
  itinerary: Itinerary | null;
}>();

type CategoryKey = "all" | "spots" | "meals" | "hotels";

const activeCategory = ref<CategoryKey>("all");
const failedImageKeys = ref(new Set<string>());

interface PlaceEntry {
  key: string;
  dayIndex: number;
  category: Exclude<CategoryKey, "all">;
  name: string;
  address: string;
  imageUrl?: string | null;
  description: string;
}

const places = computed<PlaceEntry[]>(() => {
  if (!props.itinerary) return [];
  const entries: PlaceEntry[] = [];

  for (const day of props.itinerary.days) {
    for (const spot of day.spots) {
      entries.push({
        key: `spot-${day.day_index}-${spot.name}`,
        dayIndex: day.day_index,
        category: "spots",
        name: spot.name,
        address: spot.address || spot.location || "待补充",
        imageUrl: spot.image_url,
        description: spot.description || "暂无说明",
      });
    }
    for (const meal of day.meals) {
      entries.push({
        key: `meal-${day.day_index}-${meal.name}`,
        dayIndex: day.day_index,
        category: "meals",
        name: meal.name,
        address: meal.address || "待补充",
        imageUrl: meal.image_url,
        description: meal.notes || meal.meal_type || "暂无说明",
      });
    }
    if (day.hotel) {
      entries.push({
        key: `hotel-${day.day_index}-${day.hotel.name}`,
        dayIndex: day.day_index,
        category: "hotels",
        name: day.hotel.name,
        address: day.hotel.address || day.hotel.location || "待补充",
        imageUrl: day.hotel.image_url,
        description: day.hotel.level || "住宿安排",
      });
    }
  }
  return entries;
});

const categories: { key: CategoryKey; label: string }[] = [
  { key: "all", label: "全部" },
  { key: "spots", label: "景点" },
  { key: "meals", label: "餐饮" },
  { key: "hotels", label: "住宿" },
];

const filteredPlaces = computed(() =>
  activeCategory.value === "all"
    ? places.value
    : places.value.filter((p) => p.category === activeCategory.value)
);

const categoryLabel = (category: Exclude<CategoryKey, "all">) => {
  const map: Record<Exclude<CategoryKey, "all">, string> = {
    spots: "景点",
    meals: "餐饮",
    hotels: "住宿",
  };
  return map[category];
};

function markImageAsFailed(key: string) {
  failedImageKeys.value = new Set([...failedImageKeys.value, key]);
}
</script>

<template>
  <div class="places-panel">
    <!-- 分类筛选 -->
    <div class="ws-card places-toolbar">
      <div class="ws-card__header">地点收藏</div>
      <div class="places-tabs">
        <button
          v-for="cat in categories"
          :key="cat.key"
          :class="['places-tab', { 'places-tab--active': activeCategory === cat.key }]"
          @click="activeCategory = cat.key"
        >
          {{ cat.label }}
        </button>
      </div>
      <p class="places-count">共 {{ filteredPlaces.length }} 个地点</p>
    </div>

    <!-- 地点列表 -->
    <div v-if="filteredPlaces.length" class="ws-card ws-card--full places-list">
      <div class="ws-point-grid">
        <div v-for="place in filteredPlaces" :key="place.key" class="ws-point">
          <div class="ws-point__head">
            <span>第{{ place.dayIndex }}天 · {{ place.name }}</span>
            <span>{{ categoryLabel(place.category) }}</span>
          </div>
          <img
            v-if="place.imageUrl && !failedImageKeys.has(place.key)"
            class="ws-point__img"
            :src="place.imageUrl"
            :alt="`${place.name} 图片`"
            @error="markImageAsFailed(place.key)"
          />
          <div v-else class="ws-point__img ws-point__img--empty">暂无图片</div>
          <div class="ws-point__info"><span class="ws-muted">地址：</span>{{ place.address }}</div>
          <div class="ws-point__desc">{{ place.description }}</div>
        </div>
      </div>
    </div>

    <div v-else class="ws-card ws-card--full">
      <div class="ws-empty">该行程暂无地点信息</div>
    </div>
  </div>
</template>

<style scoped>
.places-panel {
  display: grid;
  grid-template-columns: 1fr;
  gap: 12px;
}

.places-tabs {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  margin-bottom: 8px;
}

.places-tab {
  border: 1px solid #d1d1d6;
  border-radius: 20px;
  padding: 6px 14px;
  background: #ffffff;
  color: #3c3c43;
  font-size: 13px;
  cursor: pointer;
  transition: all 0.2s ease;
}

.places-tab:hover {
  border-color: #007aff;
  color: #007aff;
}

.places-tab--active {
  background: #007aff;
  border-color: #007aff;
  color: #ffffff;
}

.places-count {
  margin: 0;
  font-size: 13px;
  color: #8e8e93;
}
</style>
