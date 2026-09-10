<script setup lang="ts">
import { ref } from "vue";
import History from "./views/History.vue";
import Home from "./views/Home.vue";
import TripWorkspace from "./views/TripWorkspace.vue";
import type { Itinerary } from "./types";

const currentView = ref<"home" | "workspace" | "history">("home");
const latestItinerary = ref<Itinerary | null>(null);

function handleGenerated(itinerary: Itinerary) {
  latestItinerary.value = itinerary;
  currentView.value = "workspace";
}

function openTrip(itinerary: Itinerary) {
  latestItinerary.value = itinerary;
  currentView.value = "workspace";
}

function updateCurrentItinerary(itinerary: Itinerary) {
  latestItinerary.value = itinerary;
}

function navigateToHome() {
  currentView.value = "home";
}

function navigateToHistory() {
  currentView.value = "history";
}
</script>

<template>
  <div class="app-shell">
    <header class="nav-bar">
      <div class="nav-bar__inner">
        <span class="nav-bar__title">智能旅行助手</span>
        <div class="nav-bar__tabs">
          <button
            :class="['nav-tab', { 'nav-tab--active': currentView === 'home' }]"
            @click="currentView = 'home'"
          >
            规划
          </button>
          <button
            :class="[
              'nav-tab',
              { 'nav-tab--active': currentView === 'workspace' },
              { 'nav-tab--disabled': !latestItinerary }
            ]"
            :disabled="!latestItinerary"
            @click="currentView = 'workspace'"
          >
            工作台
          </button>
          <button
            :class="['nav-tab', { 'nav-tab--active': currentView === 'history' }]"
            @click="currentView = 'history'"
          >
            历史
          </button>
        </div>
      </div>
    </header>

    <main class="page-content">
      <Home
        v-if="currentView === 'home'"
        @generated="handleGenerated"
      />
      <TripWorkspace
        v-else-if="currentView === 'workspace'"
        :itinerary="latestItinerary"
        @back-home="navigateToHome"
        @view-history="navigateToHistory"
        @updated="updateCurrentItinerary"
      />
      <History
        v-else
        :active="currentView === 'history'"
        @open-trip="openTrip"
      />
    </main>
  </div>
</template>

<style scoped>
body {
  margin: 0;
  min-width: 320px;
  font-family: -apple-system, BlinkMacSystemFont, "SF Pro Text", "PingFang SC", "Microsoft YaHei", sans-serif;
  background: #F2F2F7;
  color: #1C1C1E;
  -webkit-font-smoothing: antialiased;
}

* {
  box-sizing: border-box;
}

.app-shell {
  min-height: 100vh;
  padding-top: 56px;
}

.nav-bar {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  z-index: 100;
  background: rgba(255, 255, 255, 0.72);
  backdrop-filter: saturate(180%) blur(20px);
  -webkit-backdrop-filter: saturate(180%) blur(20px);
  border-bottom: 0.5px solid rgba(0, 0, 0, 0.1);
}

.nav-bar__inner {
  max-width: 1440px;
  margin: 0 auto;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 20px;
  height: 56px;
}

.nav-bar__title {
  font-size: 17px;
  font-weight: 600;
  color: #1C1C1E;
}

.nav-bar__tabs {
  display: flex;
  gap: 2px;
  padding: 3px;
  border-radius: 10px;
  background: rgba(0, 0, 0, 0.04);
}

.nav-tab {
  border: none;
  border-radius: 8px;
  padding: 6px 16px;
  background: transparent;
  color: #8E8E93;
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s ease;
}

.nav-tab:active {
  transform: scale(0.97);
}

.nav-tab--active {
  background: #FFFFFF;
  color: #1C1C1E;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.08);
}

.nav-tab--disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.page-content {
  max-width: 1440px;
  margin: 0 auto;
  padding: 20px 20px 40px;
}

@media (max-width: 768px) {
  .app-shell {
    padding-top: 52px;
  }

  .nav-bar__inner {
    height: 52px;
    padding: 0 16px;
  }

  .nav-bar__title {
    font-size: 15px;
  }

  .page-content {
    padding: 16px 16px 32px;
  }
}
</style>
