import { describe, expect, it, vi } from "vitest";
import { mount } from "@vue/test-utils";

// stub 掉会动态加载高德脚本的地图组件（jsdom 中无法加载）
vi.mock("../src/components/AmapTripMap.vue", () => ({
  default: {
    name: "AmapTripMap",
    props: ["points"],
    template: "<div class='map-stub' />",
  },
}));

vi.mock("../src/services/api", () => ({
  saveTrip: vi.fn().mockResolvedValue({ message: "ok", trip_id: "t1" }),
  fetchWeatherForecast: vi.fn().mockRejectedValue(new Error("skip weather")),
  getMarkdownExportUrl: vi.fn(() => "/api/export/t1/markdown"),
  getPdfExportUrl: vi.fn(() => "/api/export/t1/pdf"),
  chatWithTrip: vi.fn(),
  editTrip: vi.fn(),
  generateTrip: vi.fn(),
}));

import TripWorkspace from "../src/views/TripWorkspace.vue";
import type { Itinerary } from "../src/types";

const itinerary: Itinerary = {
  trip_id: "trip_test",
  destination: "大理",
  summary: "测试行程",
  days: [
    {
      day_index: 1,
      date: "2026-09-06",
      theme: "轻松游",
      spots: [{ name: "大理古城", latitude: 25.69, longitude: 100.16 }],
      meals: [{ name: "烤乳扇", meal_type: "午餐" }],
      hotel: { name: "兰林阁酒店" },
      transport: [],
      notes: ["当天备注"],
    },
  ],
  estimated_budget: 2282,
  budget_breakdown: {
    transport: 131,
    hotel: 1075,
    meals: 602,
    tickets: 91,
    other: 0,
    total: 2282,
  },
  tips: ["带伞"],
  source_notes: [],
};

function mountWorkspace() {
  return mount(TripWorkspace, {
    props: { itinerary },
    global: {
      stubs: {
        // 过滤 ant-design-vue message 等，无需真实注册
      },
    },
  });
}

describe("TripWorkspace 三栏工作台", () => {
  it("渲染 AI 助手面板（右侧栏默认展开）", () => {
    const wrapper = mountWorkspace();
    expect(wrapper.find(".ai-side").exists()).toBe(true);
    expect(wrapper.find(".ai-panel").exists()).toBe(true);
    expect(wrapper.find(".ai-panel__title").text()).toContain("AI 助手");
  });

  it("AI 助手可收起为悬浮按钮（不占布局空间）并再展开", async () => {
    const wrapper = mountWorkspace();
    await wrapper.find(".ai-panel__collapse").trigger("click");
    expect(wrapper.find(".ai-fab").exists()).toBe(true);
    expect(wrapper.find(".ai-side").exists()).toBe(false);
    expect(wrapper.find(".ai-panel").exists()).toBe(false);

    await wrapper.find(".ai-fab").trigger("click");
    expect(wrapper.find(".ai-panel").exists()).toBe(true);
  });

  it("渲染左栏导航与中栏面板", () => {
    const wrapper = mountWorkspace();
    expect(wrapper.find(".trip-nav").exists()).toBe(true);
    expect(wrapper.find(".overview-panel").exists()).toBe(true);
  });
});
