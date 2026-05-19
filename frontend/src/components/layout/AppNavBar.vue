<script setup lang="ts">
import { RouterLink } from 'vue-router'
import { useBackendHealth } from '@/composables/useBackendHealth'

const { statusText, statusTitle, connected } = useBackendHealth()
</script>

<template>
  <nav class="app-nav">
    <RouterLink to="/" class="brand">ChatBI</RouterLink>
    <div class="nav-right">
      <RouterLink to="/training" class="nav-link">语料管理</RouterLink>
      <span
        class="status-badge"
        :class="{ error: !connected && statusText.includes('未连接') }"
        :title="statusTitle"
      >
        {{ statusText }}
      </span>
    </div>
  </nav>
</template>

<style scoped>
.app-nav {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 24px;
  background: rgba(255, 255, 255, 0.72);
  backdrop-filter: blur(8px);
  border-bottom: 1px solid rgba(226, 232, 240, 0.8);
}

.brand {
  font-weight: 700;
  font-size: 16px;
  color: #5b21b6;
  text-decoration: none;
}

.nav-right {
  display: flex;
  align-items: center;
  gap: 16px;
}

.nav-link {
  font-size: 13px;
  color: #64748b;
  text-decoration: none;
}

.nav-link:hover,
.nav-link.router-link-active {
  color: #6d28d9;
}

.status-badge {
  font-size: 11px;
  color: #059669;
  background: #d1fae5;
  padding: 4px 10px;
  border-radius: 20px;
  max-width: 200px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.status-badge.error {
  color: #b91c1c;
  background: #fee2e2;
}
</style>
