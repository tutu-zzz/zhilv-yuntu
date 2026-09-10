<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from "vue";

interface TripMapPoint {
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

const props = defineProps<{
  points: TripMapPoint[];
}>();

declare global {
  interface Window {
    AMap?: any;
  }
}

const mapContainer = ref<HTMLDivElement | null>(null);
const mapInstance = ref<any>(null);
const markerList = ref<any[]>([]);
const routeLine = ref<any>(null);
const loadError = ref("");

const amapKey = import.meta.env.VITE_AMAP_JS_KEY;

const validPoints = computed(() =>
  props.points.filter(
    (point) => point.longitude != null && point.latitude != null
  )
);

function clearOverlays() {
  if (!mapInstance.value) {
    return;
  }

  markerList.value.forEach((marker) => {
    mapInstance.value.remove(marker);
  });
  markerList.value = [];

  if (routeLine.value) {
    mapInstance.value.remove(routeLine.value);
    routeLine.value = null;
  }
}

function renderMarkers() {
  if (!window.AMap || !mapInstance.value) {
    return;
  }

  clearOverlays();

  const sorted = [...validPoints.value].sort((a, b) => a.dayIndex - b.dayIndex);
  const bounds: [number, number][] = [];
  const routePath: [number, number][] = [];

  sorted.forEach((point) => {
    const position: [number, number] = [point.longitude as number, point.latitude as number];
    bounds.push(position);
    routePath.push(position);

    const marker = new window.AMap.Marker({
      position,
      title: point.name,
      offset: new window.AMap.Pixel(-12, -28),
      content: `
        <div style="position:relative;display:flex;flex-direction:column;align-items:center;">
          <div style="font-size:22px;line-height:1;">🚩</div>
          <div style="
            margin-top:2px;
            padding:2px 7px;
            border-radius:999px;
            background:linear-gradient(135deg,#6d82de,#8a67cf);
            color:#fff;
            font-size:11px;
            font-weight:700;
            white-space:nowrap;
            box-shadow:0 2px 6px rgba(0,0,0,0.18);
          ">D${point.dayIndex}</div>
        </div>
      `,
    });

    const imageHtml = point.imageUrl
      ? `<img src="${point.imageUrl}" alt="${point.name}" style="width:100%;height:100%;object-fit:cover;border-radius:8px;" />`
      : `<div style="width:100%;height:100%;display:grid;place-items:center;border-radius:8px;background:linear-gradient(135deg,#e8edff,#f0e8ff);color:#8b8fad;font-size:10px;">暂无图片</div>`;

    const bubble = new window.AMap.Marker({
      position,
      offset: new window.AMap.Pixel(14, -46),
      content: `
        <div style="
          position:relative;
          width:110px;
          background:#fff;
          border-radius:10px;
          box-shadow:0 3px 12px rgba(0,0,0,0.12);
          overflow:hidden;
          font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;
        ">
          <div style="width:110px;height:72px;overflow:hidden;background:#eef3ff;">
            ${imageHtml}
          </div>
          <div style="padding:5px 8px 6px;">
            <div style="font-size:11px;font-weight:600;color:#2d3748;line-height:1.3;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">${point.name}</div>
          </div>
          <div style="
            position:absolute;
            left:-5px;
            top:30px;
            width:0;
            height:0;
            border-top:5px solid transparent;
            border-bottom:5px solid transparent;
            border-right:5px solid #fff;
            filter:drop-shadow(-2px 0 2px rgba(0,0,0,0.06));
          "></div>
        </div>
      `,
      zIndex: 100,
    });

    const infoWindow = new window.AMap.InfoWindow({
      offset: new window.AMap.Pixel(0, -32),
      content: `
        <div style="max-width:240px;padding:4px 2px;line-height:1.7;">
          <strong>${point.name}</strong><br/>
          <span>第${point.dayIndex}天 · ${point.theme}</span><br/>
          <span>${point.address}</span>
        </div>
      `,
    });

    marker.on("click", () => {
      infoWindow.open(mapInstance.value, position);
    });

    mapInstance.value.add(marker);
    mapInstance.value.add(bubble);
    markerList.value.push(marker);
    markerList.value.push(bubble);
  });

  if (routePath.length >= 2) {
    routeLine.value = new window.AMap.Polyline({
      path: routePath,
      strokeColor: "#6d82de",
      strokeWeight: 3,
      strokeOpacity: 0.8,
      strokeStyle: "dashed",
      strokeDasharray: [10, 6],
      lineJoin: "round",
      lineCap: "round",
      showDir: true,
      dirColor: "#6d82de",
      dirSize: 8,
      borderWeight: 1,
      borderColor: "rgba(109,130,222,0.25)",
      zIndex: 50,
    });
    mapInstance.value.add(routeLine.value);
  }

  if (bounds.length === 1) {
    mapInstance.value.setZoomAndCenter(13, bounds[0]);
  } else if (bounds.length > 1) {
    mapInstance.value.setFitView(markerList.value, false, [60, 60, 60, 60]);
  }
}

function ensureMapScript(): Promise<void> {
  return new Promise((resolve, reject) => {
    if (window.AMap) {
      resolve();
      return;
    }

    const existingScript = document.querySelector<HTMLScriptElement>(
      'script[data-amap-loader="true"]'
    );

    if (existingScript) {
      existingScript.addEventListener("load", () => resolve(), { once: true });
      existingScript.addEventListener("error", () => reject(new Error("高德地图脚本加载失败。")), {
        once: true,
      });
      return;
    }

    const script = document.createElement("script");
    // 使用 JS API 1.4.x：2.0 强制要求配置安全密钥（securityJsCode），
    // 未配置时底图瓦片不加载（白图）但覆盖物正常，表现为"地图空白"。
    // 如需升级 2.0，需在加载脚本前设置 window._AMapSecurityConfig。
    script.src = `https://webapi.amap.com/maps?v=1.4.15&key=${amapKey}`;
    script.async = true;
    script.defer = true;
    script.dataset.amapLoader = "true";
    script.onload = () => resolve();
    script.onerror = () => reject(new Error("高德地图脚本加载失败。"));
    document.head.appendChild(script);
  });
}

async function initMap() {
  if (!amapKey) {
    loadError.value = "未配置前端高德 JavaScript Key。";
    return;
  }

  if (!mapContainer.value) {
    return;
  }

  try {
    loadError.value = "";
    await ensureMapScript();

    if (!window.AMap) {
      loadError.value = "高德地图对象初始化失败。";
      return;
    }

    mapInstance.value = new window.AMap.Map(mapContainer.value, {
      zoom: 11,
      resizeEnable: true,
      viewMode: "2D",
      mapStyle: "amap://styles/whitesmoke",
    });

    renderMarkers();
  } catch (error) {
    console.error(error);
    loadError.value = "地图加载失败，请检查前端高德 Key 或网络环境。";
  }
}

onMounted(() => {
  void initMap();
});

watch(validPoints, () => {
  if (mapInstance.value) {
    renderMarkers();
  }
});

onBeforeUnmount(() => {
  clearOverlays();
  if (mapInstance.value) {
    mapInstance.value.destroy();
    mapInstance.value = null;
  }
});
</script>

<template>
  <div class="trip-map">
    <div v-if="loadError" class="trip-map__placeholder">
      <strong>地图暂未启用</strong>
      <span>{{ loadError }}</span>
    </div>
    <div v-else-if="validPoints.length === 0" class="trip-map__placeholder">
      <strong>暂无可展示点位</strong>
      <span>当前 itinerary 里还没有可用的经纬度数据。</span>
    </div>
    <div v-else ref="mapContainer" class="trip-map__canvas"></div>
  </div>
</template>

<style scoped>
.trip-map {
  height: calc(100% - 58px);
  min-height: 280px;
}

.trip-map__canvas,
.trip-map__placeholder {
  width: 100%;
  height: 100%;
  min-height: 280px;
  border-radius: 20px;
}

.trip-map__placeholder {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 10px;
  padding: 20px;
  background:
    linear-gradient(135deg, rgba(129, 179, 255, 0.18), rgba(137, 108, 230, 0.15)),
    linear-gradient(45deg, rgba(255, 255, 255, 0.75), rgba(244, 247, 255, 0.9));
  color: #5b6474;
  text-align: center;
}

.trip-map__placeholder strong {
  font-size: 22px;
  color: #4b5563;
}

.trip-map__placeholder span {
  max-width: 360px;
  color: #7b8494;
  line-height: 1.7;
}
</style>
