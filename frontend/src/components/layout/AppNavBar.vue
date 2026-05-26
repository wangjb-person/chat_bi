<script setup lang="ts">
import { RouterLink } from 'vue-router'
import { ArrowDown } from '@element-plus/icons-vue'
import { useBackendHealth } from '@/composables/useBackendHealth'
import { CURRENT_USER, userAvatarText } from '@/constants/user'

const { statusText, statusTitle, connected } = useBackendHealth()
const avatarLetter = userAvatarText(CURRENT_USER.displayName)
</script>

<template>
  <nav class="app-nav">
    <RouterLink to="/" class="brand">ChatBI</RouterLink>
    <div class="nav-right">
      <RouterLink to="/metrics" class="nav-link">指标管理</RouterLink>
      <RouterLink to="/training" class="nav-link">语料管理</RouterLink>
      <RouterLink to="/knowledge" class="nav-link">知识库</RouterLink>
      <el-dropdown trigger="click" placement="bottom-end">
        <button type="button" class="user-profile" aria-label="用户菜单">
          <span class="avatar-wrap">
            <el-avatar :size="32" class="user-avatar">{{ avatarLetter }}</el-avatar>
            <span
              class="conn-dot"
              :class="{ online: connected, offline: !connected }"
              :title="statusTitle"
            />
          </span>
          <span class="user-name">{{ CURRENT_USER.displayName }}</span>
          <el-icon class="user-caret"><ArrowDown /></el-icon>
        </button>
        <template #dropdown>
          <el-dropdown-menu>
            <el-dropdown-item disabled class="menu-account">
              <span class="menu-label">账号</span>
              <span class="menu-value">{{ CURRENT_USER.username }}</span>
            </el-dropdown-item>
            <el-dropdown-item disabled>
              <span
                class="menu-status"
                :class="{ 'menu-status--error': !connected }"
                :title="statusTitle"
              >
                {{ statusText }}
              </span>
            </el-dropdown-item>
          </el-dropdown-menu>
        </template>
      </el-dropdown>
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

.user-profile {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 4px 8px 4px 4px;
  border: none;
  border-radius: 24px;
  background: transparent;
  cursor: pointer;
  transition: background 0.15s ease;
}

.user-profile:hover {
  background: rgba(109, 40, 217, 0.06);
}

.avatar-wrap {
  position: relative;
  flex-shrink: 0;
}

.user-avatar {
  background: linear-gradient(135deg, #7c3aed 0%, #5b21b6 100%);
  color: #fff;
  font-size: 14px;
  font-weight: 600;
}

.conn-dot {
  position: absolute;
  right: -1px;
  bottom: -1px;
  width: 10px;
  height: 10px;
  border: 2px solid #fff;
  border-radius: 50%;
  box-sizing: border-box;
}

.conn-dot.online {
  background: #10b981;
}

.conn-dot.offline {
  background: #ef4444;
}

.user-name {
  font-size: 13px;
  font-weight: 500;
  color: #334155;
  max-width: 120px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.user-caret {
  font-size: 12px;
  color: #94a3b8;
}

.menu-account {
  display: flex;
  flex-direction: column;
  gap: 2px;
  line-height: 1.4;
}

.menu-label {
  font-size: 11px;
  color: #94a3b8;
}

.menu-value {
  font-size: 13px;
  color: #334155;
}

.menu-status {
  font-size: 12px;
  color: #059669;
}

.menu-status--error {
  color: #b91c1c;
}
</style>
