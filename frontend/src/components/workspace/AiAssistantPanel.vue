<script setup lang="ts">
import { nextTick, ref, watch } from "vue";
import axios from "axios";
import { message } from "ant-design-vue";
import { chatWithTrip } from "../../services/api";
import type {
  ChatMessage,
  Itinerary,
  TripChatPayload,
} from "../../types";

const props = defineProps<{
  itinerary: Itinerary | null;
  selectedDay: number;
  collapsed: boolean;
}>();

const emit = defineEmits<{
  updated: [itinerary: Itinerary];
  toggle: [];
}>();

const messages = ref<ChatMessage[]>([]);
const inputText = ref("");
const sending = ref(false);
const sendingStatus = ref("");
const messagesContainer = ref<HTMLDivElement | null>(null);

const quickInstructions = [
  "这一天节奏更轻松一点",
  "安排得更充实一点",
  "增加更多美食",
  "减少交通耗时",
  "增加适合拍照的景点",
];

// 行程切换（新行程/历史打开）时重置对话
watch(
  () => props.itinerary?.trip_id,
  () => {
    messages.value = [
      {
        role: "assistant",
        content: `你好！我是你的行程助手。当前选中第 ${props.selectedDay} 天，直接告诉我想怎么调整，或者问我任何旅行问题。`,
      },
    ];
  },
  { immediate: true }
);

watch(
  () => props.selectedDay,
  (dayIndex) => {
    // 仅追加一条轻量提示，不打断既有对话
    if (messages.value.length > 1) {
      messages.value.push({
        role: "assistant",
        content: `已切换到第 ${dayIndex} 天，想调整这一天直接说～`,
      });
      scrollToBottom();
    }
  }
);

async function scrollToBottom() {
  await nextTick();
  if (messagesContainer.value) {
    messagesContainer.value.scrollTop = messagesContainer.value.scrollHeight;
  }
}

async function sendMessage(textOverride?: string) {
  if (!props.itinerary || sending.value) return;
  const content = (textOverride ?? inputText.value).trim();
  if (!content) {
    message.warning("请先输入内容。");
    return;
  }

  const history = [...messages.value, { role: "user" as const, content }];
  messages.value = history;
  inputText.value = "";
  sending.value = true;
  sendingStatus.value = "正在理解你的需求...";
  void scrollToBottom();

  const statusTimer = window.setTimeout(() => {
    sendingStatus.value = "正在整理回复...";
  }, 1500);

  try {
    const payload: TripChatPayload = {
      trip_id: props.itinerary.trip_id,
      current_itinerary: props.itinerary,
      messages: history,
      context: {
        active_panel: "itinerary",
        selected_day: props.selectedDay,
      },
    };
    const result = await chatWithTrip(payload);

    messages.value.push({ role: "assistant", content: result.reply });

    if (result.changed && result.itinerary) {
      emit("updated", result.itinerary);
      message.success("行程已根据对话更新。");
    }
  } catch (error) {
    console.error(error);
    // 优先透出后端的明确错误（如模型额度耗尽），避免黑盒失败
    const detail = axios.isAxiosError(error)
      ? (error.response?.data as { detail?: string } | undefined)?.detail
      : null;
    messages.value.push({
      role: "assistant",
      content:
        detail ||
        "这次没有处理成功，你的行程没有受到影响。请稍后再试。",
    });
    if (detail) {
      message.error(detail);
    }
  } finally {
    window.clearTimeout(statusTimer);
    sending.value = false;
    sendingStatus.value = "";
    void scrollToBottom();
  }
}

function handleKeydown(event: KeyboardEvent) {
  if (event.key === "Enter" && !event.shiftKey) {
    event.preventDefault();
    void sendMessage();
  }
}
</script>

<template>
  <!-- 收起态：悬浮小按钮（fixed 定位，完全不占布局空间） -->
  <button
    v-if="collapsed"
    class="ai-fab"
    title="展开 AI 助手"
    @click="emit('toggle')"
  >
    AI
  </button>

  <!-- 展开态：右侧对话面板 -->
  <aside v-else class="ai-side">
    <div class="ai-panel">
      <div class="ai-panel__header">
        <div>
          <div class="ai-panel__title">AI 助手</div>
          <div class="ai-panel__subtitle">聊聊就能改行程</div>
        </div>
        <button class="ai-panel__collapse" title="收起" @click="emit('toggle')">▶</button>
      </div>

      <!-- 消息列表 -->
      <div ref="messagesContainer" class="ai-messages">
        <div
          v-for="(msg, index) in messages"
          :key="index"
          :class="['ai-msg', msg.role === 'user' ? 'ai-msg--user' : 'ai-msg--assistant']"
        >
          <div v-if="msg.role === 'assistant'" class="ai-avatar">AI</div>
          <div class="ai-bubble">{{ msg.content }}</div>
        </div>

        <!-- 发送中状态 -->
        <div v-if="sending" class="ai-msg ai-msg--assistant">
          <div class="ai-avatar">AI</div>
          <div class="ai-bubble ai-bubble--status">
            {{ sendingStatus }}
            <span class="ai-status__dots">
              <span></span>
              <span></span>
              <span></span>
            </span>
          </div>
        </div>
      </div>

      <!-- 快捷指令 -->
      <div class="ai-quick-actions">
        <button
          v-for="instr in quickInstructions"
          :key="instr"
          class="ai-quick-action"
          :disabled="sending"
          @click="($event) => sendMessage(instr)"
        >
          {{ instr }}
        </button>
      </div>

      <!-- 输入区 -->
      <div class="ai-input-area">
        <textarea
          v-model="inputText"
          class="ai-textarea"
          rows="2"
          :disabled="sending || !itinerary"
          :placeholder="itinerary ? '想怎么调整？直接说，Enter 发送' : '先创建一个行程再来聊～'"
          @keydown="handleKeydown"
        />
        <button
          class="ai-send-btn"
          :disabled="sending || !itinerary"
          @click="($event) => sendMessage()"
        >
          {{ sending ? "..." : "发送" }}
        </button>
      </div>
    </div>
  </aside>
</template>

<style scoped>
.ai-side {
  position: sticky;
  top: 76px;
  height: calc(100vh - 96px);
}

/* ============ 收起态：悬浮小按钮（不占布局空间） ============ */
.ai-fab {
  position: fixed;
  top: 68px;
  right: 20px;
  z-index: 90;
  width: 44px;
  height: 44px;
  border: none;
  border-radius: 12px;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: #ffffff;
  font-size: 14px;
  font-weight: 700;
  letter-spacing: 0.5px;
  cursor: pointer;
  box-shadow: 0 4px 12px rgba(102, 126, 234, 0.35);
  transition: transform 0.2s ease, box-shadow 0.2s ease;
}

.ai-fab:hover {
  transform: scale(1.06);
  box-shadow: 0 6px 16px rgba(102, 126, 234, 0.45);
}

/* ============ 展开态：对话窗口 ============ */
.ai-panel {
  height: 100%;
  display: flex;
  flex-direction: column;
  border-radius: 12px;
  background: #ffffff;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.08);
  overflow: hidden;
  animation: ai-panel-in 0.25s ease;
}

@keyframes ai-panel-in {
  from {
    opacity: 0;
    transform: translateX(12px);
  }
  to {
    opacity: 1;
    transform: translateX(0);
  }
}

.ai-panel__header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 14px 16px;
  border-bottom: 0.5px solid rgba(0, 0, 0, 0.08);
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: #ffffff;
  flex-shrink: 0;
}

.ai-panel__title {
  font-size: 16px;
  font-weight: 700;
}

.ai-panel__subtitle {
  font-size: 12px;
  opacity: 0.85;
}

.ai-panel__collapse {
  width: 28px;
  height: 28px;
  border: none;
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.2);
  color: #ffffff;
  font-size: 12px;
  cursor: pointer;
  transition: background 0.2s ease;
}

.ai-panel__collapse:hover {
  background: rgba(255, 255, 255, 0.35);
}

/* 消息列表 */
.ai-messages {
  flex: 1;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 12px;
}

.ai-msg {
  display: flex;
  gap: 8px;
  align-items: flex-end;
}

.ai-msg--user {
  justify-content: flex-end;
}

.ai-msg--assistant {
  justify-content: flex-start;
}

.ai-avatar {
  width: 28px;
  height: 28px;
  border-radius: 50%;
  display: grid;
  place-items: center;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: #ffffff;
  font-size: 11px;
  font-weight: 700;
  flex-shrink: 0;
}

.ai-bubble {
  max-width: 82%;
  padding: 8px 12px;
  border-radius: 12px;
  font-size: 13px;
  line-height: 1.6;
  white-space: pre-wrap;
  word-break: break-word;
}

.ai-msg--assistant .ai-bubble {
  background: #f2f2f7;
  color: #1c1c1e;
  border-bottom-left-radius: 4px;
}

.ai-msg--user .ai-bubble {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: #ffffff;
  border-bottom-right-radius: 4px;
}

.ai-bubble--status {
  display: flex;
  align-items: center;
  gap: 8px;
  color: #636366;
}

.ai-status__dots {
  display: inline-flex;
  gap: 3px;
}

.ai-status__dots span {
  width: 5px;
  height: 5px;
  border-radius: 50%;
  background: #667eea;
  animation: ai-status-pulse 1.4s infinite ease-in-out;
}

.ai-status__dots span:nth-child(1) {
  animation-delay: -0.32s;
}

.ai-status__dots span:nth-child(2) {
  animation-delay: -0.16s;
}

@keyframes ai-status-pulse {
  0%,
  80%,
  100% {
    opacity: 0.4;
  }
  40% {
    opacity: 1;
  }
}

/* 快捷指令 */
.ai-quick-actions {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
  padding: 0 12px 8px;
  flex-shrink: 0;
}

.ai-quick-action {
  padding: 5px 10px;
  border: 1px solid rgba(0, 122, 255, 0.3);
  border-radius: 16px;
  background: transparent;
  color: #007aff;
  font-size: 12px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s ease;
}

.ai-quick-action:hover:not(:disabled) {
  background: #eaf2ff;
  border-color: rgba(0, 122, 255, 0.6);
}

.ai-quick-action:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

/* 输入区 */
.ai-input-area {
  display: flex;
  gap: 8px;
  align-items: flex-end;
  padding: 10px 12px 12px;
  border-top: 0.5px solid rgba(0, 0, 0, 0.06);
  flex-shrink: 0;
}

.ai-textarea {
  flex: 1;
  min-height: 52px;
  max-height: 120px;
  padding: 10px 12px;
  border: 1px solid #d1d1d6;
  border-radius: 10px;
  font-size: 14px;
  color: #1c1c1e;
  background: #ffffff;
  outline: none;
  resize: none;
  font-family: inherit;
  transition: border-color 0.2s ease;
}

.ai-textarea:focus {
  border-color: #667eea;
}

.ai-send-btn {
  border: none;
  border-radius: 10px;
  padding: 10px 16px;
  font-size: 14px;
  font-weight: 600;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: #ffffff;
  cursor: pointer;
  transition: all 0.2s ease;
  flex-shrink: 0;
}

.ai-send-btn:hover:not(:disabled) {
  opacity: 0.92;
}

.ai-send-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}
</style>
