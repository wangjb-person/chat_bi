<script setup lang="ts">
import ChatPanel from '@/components/chat/ChatPanel.vue'
import TrainingSidebar from '@/components/training/TrainingSidebar.vue'
</script>

<template>
  <div class="layout">
    <TrainingSidebar />
    <ChatPanel />
  </div>
</template>

<style scoped>
.layout {
  display: flex;
  height: 100%;
}
</style>
