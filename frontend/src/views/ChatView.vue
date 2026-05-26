<script setup lang="ts">
import { computed } from 'vue'
import { storeToRefs } from 'pinia'
import AppNavBar from '@/components/layout/AppNavBar.vue'
import AskModeSwitch from '@/components/chat/AskModeSwitch.vue'
import ChatHero from '@/components/chat/ChatHero.vue'
import ChatComposer from '@/components/chat/ChatComposer.vue'
import ExampleQuestionChips from '@/components/chat/ExampleQuestionChips.vue'
import ConversationSidebar from '@/components/chat/ConversationSidebar.vue'
import MessageList from '@/components/chat/MessageList.vue'
import { useChatStore } from '@/stores/chatStore'

const chat = useChatStore()
const { messages, sending } = storeToRefs(chat)
const hasConversation = computed(() =>
  messages.value.some((m) => m.role === 'user'),
)

function onAsk(question: string) {
  void chat.sendQuestion(question)
}

function onExampleSelect(question: string) {
  void chat.sendQuestion(question)
}
</script>

<template>
  <div class="chat-page">
    <AppNavBar />

    <div class="chat-body">
      <ConversationSidebar />

      <main class="chat-main" :class="{ conversation: hasConversation }">
        <section v-if="!hasConversation" class="landing">
          <div class="mode-row">
            <AskModeSwitch />
          </div>
          <ChatHero />
          <div class="landing-composer">
            <ChatComposer @submit="onAsk" />
            <ExampleQuestionChips @select="onExampleSelect" />
          </div>
        </section>

        <template v-else>
          <MessageList class="message-scroll" />
          <section class="bottom-composer" :class="{ disabled: sending }">
            <div class="mode-row mode-row--compact">
              <AskModeSwitch />
            </div>
            <ChatComposer @submit="onAsk" />
            <ExampleQuestionChips @select="onExampleSelect" />
          </section>
        </template>
      </main>
    </div>
  </div>
</template>

<style scoped>
.chat-page {
  min-height: 100%;
  display: flex;
  flex-direction: column;
  background:
    radial-gradient(ellipse 80% 50% at 50% -10%, rgba(196, 181, 253, 0.35), transparent),
    radial-gradient(circle at 10% 20%, rgba(224, 231, 255, 0.5), transparent 40%),
    radial-gradient(circle at 90% 80%, rgba(237, 233, 254, 0.6), transparent 45%),
    #f5f3ff;
}

.chat-body {
  flex: 1;
  display: flex;
  min-height: 0;
}

.chat-main {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 0;
  min-width: 0;
}

.chat-main.conversation {
  overflow: hidden;
}

.mode-row {
  margin-bottom: 20px;
  display: flex;
  justify-content: center;
}

.mode-row--compact {
  margin-bottom: 10px;
  width: 100%;
  max-width: 920px;
}

.landing {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 24px 20px 48px;
}

.landing-composer {
  width: 100%;
  max-width: 920px;
  display: flex;
  flex-direction: column;
  align-items: center;
}

.message-scroll {
  flex: 1;
  min-height: 0;
}

.message-scroll :deep(.messages) {
  max-width: 920px;
  margin: 0 auto;
  padding: 20px 24px 12px;
}

.bottom-composer {
  flex-shrink: 0;
  padding: 12px 20px 20px;
  background: linear-gradient(180deg, transparent, rgba(245, 243, 255, 0.95) 24%);
  display: flex;
  flex-direction: column;
  align-items: center;
}

.bottom-composer :deep(.composer-card),
.bottom-composer :deep(.example-row) {
  max-width: 920px;
}
</style>
