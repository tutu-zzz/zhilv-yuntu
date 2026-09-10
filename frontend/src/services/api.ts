import axios from "axios";

import type {
  Itinerary,
  TripChatPayload,
  TripChatResponse,
  TripDetailResponse,
  TripEditPayload,
  TripListResponse,
  TripRequestPayload,
  TripSaveResponse,
  WeatherForecastResponse,
} from "../types";

// 默认走同源 /api（开发环境由 Vite proxy 转发，生产由 Nginx 转发），
// 本机 IP 变化无需改配置；仅直连部署时才需要设置 VITE_API_BASE_URL。
export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "/api";

const api = axios.create({
  baseURL: API_BASE_URL,
  // 生成行程链路（RAG + LLM + 地图补全）实测可达 90s+，峰值波动会更高，
  // 120s 会导致前端超时而后端仍在正常执行。放宽到 300s。
  timeout: 300000,
});

export async function generateTrip(payload: TripRequestPayload): Promise<Itinerary> {
  const response = await api.post<Itinerary>("/trip/generate", payload);
  return response.data;
}

export async function editTrip(payload: TripEditPayload): Promise<Itinerary> {
  const response = await api.post<Itinerary>("/trip/edit", payload);
  return response.data;
}

export async function chatWithTrip(payload: TripChatPayload): Promise<TripChatResponse> {
  const response = await api.post<TripChatResponse>("/trip/chat", payload);
  return response.data;
}

export async function saveTrip(itinerary: Itinerary): Promise<TripSaveResponse> {
  const response = await api.post<TripSaveResponse>("/trip/save", {
    trip_id: itinerary.trip_id,
    itinerary,
    user_id: "frontend_demo_user",
  });
  return response.data;
}

export async function listTrips(): Promise<TripListResponse> {
  const response = await api.get<TripListResponse>("/trip");
  return response.data;
}

export async function getTripDetail(tripId: string): Promise<TripDetailResponse> {
  const response = await api.get<TripDetailResponse>(`/trip/${tripId}`);
  return response.data;
}

export async function deleteTrip(tripId: string): Promise<void> {
  await api.delete(`/trip/${tripId}`);
}

export async function fetchWeatherForecast(city: string): Promise<WeatherForecastResponse> {
  const response = await api.get<WeatherForecastResponse>("/weather/forecast", {
    params: { city },
  });
  return response.data;
}

export function getMarkdownExportUrl(tripId: string): string {
  return `${API_BASE_URL}/export/${encodeURIComponent(tripId)}/markdown`;
}

export function getPdfExportUrl(tripId: string): string {
  return `${API_BASE_URL}/export/${encodeURIComponent(tripId)}/pdf`;
}

export default api;
