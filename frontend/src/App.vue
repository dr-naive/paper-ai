<template>
  <a-config-provider :locale="zhCN">
    <router-view />
  </a-config-provider>
</template>

<script setup lang="ts">
import zhCN from '@arco-design/web-vue/es/locale/lang/zh-cn'
</script>

<style>
:root {
  --pa-primary: oklch(0.50 0.16 45);
  --pa-primary-hover: oklch(0.45 0.18 45);
  --pa-primary-soft: oklch(0.95 0.035 55);
  --pa-ink: oklch(0.22 0.025 45);
  --pa-text: oklch(0.34 0.022 50);
  --pa-muted: oklch(0.50 0.018 50);
  --pa-bg: oklch(0.975 0.008 55);
  --pa-surface: oklch(0.995 0.003 55);
  --pa-surface-soft: oklch(0.96 0.012 55);
  --pa-border: oklch(0.88 0.018 55);
  --pa-info: oklch(0.51 0.12 250);
  --pa-info-soft: oklch(0.96 0.018 250);
  --pa-success: oklch(0.52 0.12 145);
  --pa-danger: oklch(0.52 0.17 28);
  --pa-toolbar: oklch(0.28 0.018 45);
  --pa-toolbar-control: oklch(0.36 0.02 45);
}

* { margin: 0; padding: 0; box-sizing: border-box; }
html, body, #app {
  width: 100%;
  min-height: 100%;
  color-scheme: light;
}
body {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
  color: var(--pa-ink);
  background: var(--pa-bg);
}

/* ===== 全局 Arco 暖色调主题 ===== */

/* 按钮 */
.arco-btn-primary {
  background: var(--pa-primary) !important;
  border-color: var(--pa-primary) !important;
  color: oklch(0.98 0.01 95) !important;
}

.arco-btn-primary:hover {
  background: var(--pa-primary-hover) !important;
  border-color: var(--pa-primary-hover) !important;
}

.arco-btn-secondary {
  background: oklch(0.95 0.01 90) !important;
  border-color: oklch(0.50 0.16 45 / 0.3) !important;
  color: oklch(0.30 0.02 50) !important;
}

.arco-btn-secondary:hover {
  background: oklch(0.50 0.16 45 / 0.08) !important;
  border-color: oklch(0.50 0.16 45) !important;
  color: oklch(0.25 0.02 50) !important;
}

.arco-btn-text {
  color: oklch(0.45 0.02 50) !important;
}

.arco-btn-text:hover {
  color: var(--pa-primary-hover) !important;
  background: var(--pa-primary-soft) !important;
}

/* 输入框 */
.arco-input-wrapper,
.arco-input-password {
  background: oklch(0.98 0.01 95) !important;
  border-color: oklch(0.85 0.01 60 / 0.3) !important;
  color: oklch(0.25 0.02 50) !important;
}

.arco-input-wrapper:hover,
.arco-input-password:hover {
  border-color: oklch(0.50 0.16 45 / 0.5) !important;
}

.arco-input-wrapper:focus-within,
.arco-input-password:focus-within {
  border-color: oklch(0.50 0.16 45) !important;
  box-shadow: 0 0 0 2px oklch(0.50 0.16 45 / 0.15) !important;
}

.arco-input {
  color: oklch(0.25 0.02 50) !important;
}

.arco-input::placeholder {
  color: oklch(0.60 0.01 50) !important;
}

/* 表单标签 */
.arco-form-item-label {
  color: oklch(0.30 0.02 50) !important;
}

/* 链接 */
.arco-link {
  color: oklch(0.45 0.14 45) !important;
}

.arco-link:hover {
  color: oklch(0.40 0.16 45) !important;
}

/* 列表 */
.arco-list-item {
  border-bottom-color: oklch(0.85 0.01 60 / 0.15) !important;
}

.arco-list-item-meta-title {
  color: oklch(0.20 0.02 50) !important;
}

.arco-list-item-meta-description {
  color: oklch(0.45 0.02 50) !important;
}

/* 下拉菜单 */
.arco-dropdown-menu {
  background: oklch(0.98 0.01 95) !important;
  border-color: oklch(0.85 0.01 60 / 0.2) !important;
  box-shadow: 0 4px 16px oklch(0 0 / 0.1) !important;
}

.arco-dropdown-option {
  color: oklch(0.30 0.02 50) !important;
}

.arco-dropdown-option:hover {
  background: oklch(0.50 0.16 45 / 0.1) !important;
}

/* 模态框 */
.arco-modal {
  background: oklch(0.98 0.01 95) !important;
  border-color: oklch(0.85 0.01 60 / 0.2) !important;
}

.arco-modal-title {
  color: oklch(0.20 0.02 50) !important;
}

.arco-modal-header {
  border-bottom-color: oklch(0.85 0.01 60 / 0.15) !important;
}

.arco-modal-body {
  color: oklch(0.35 0.02 50) !important;
}

/* Tabs */
.arco-tabs-header {
  border-bottom-color: oklch(0.85 0.01 60 / 0.15) !important;
}

.arco-tabs-tab {
  color: oklch(0.50 0.02 50) !important;
}

.arco-tabs-tab-active {
  color: oklch(0.45 0.14 45) !important;
}

.arco-tabs-tab:hover {
  color: oklch(0.40 0.14 45) !important;
}

/* 选择器 */
.arco-select-view {
  background: oklch(0.98 0.01 95) !important;
  border-color: oklch(0.85 0.01 60 / 0.3) !important;
  color: oklch(0.25 0.02 50) !important;
}

.arco-select-view:hover {
  border-color: oklch(0.50 0.16 45 / 0.5) !important;
}

.arco-select-dropdown {
  background: oklch(0.98 0.01 95) !important;
  border-color: oklch(0.85 0.01 60 / 0.2) !important;
}

.arco-select-option {
  color: oklch(0.30 0.02 50) !important;
}

.arco-select-option:hover {
  background: oklch(0.50 0.16 45 / 0.1) !important;
}

/* 单选按钮组 */
.arco-radio-group-button .arco-radio-button {
  background: oklch(0.95 0.01 90) !important;
  border-color: oklch(0.85 0.01 60 / 0.3) !important;
  color: oklch(0.40 0.02 50) !important;
}

.arco-radio-group-button .arco-radio-button-checked {
  background: oklch(0.50 0.16 45) !important;
  border-color: oklch(0.50 0.16 45) !important;
  color: oklch(0.98 0.01 95) !important;
}

/* 上传组件 */
.arco-upload {
  color: oklch(0.40 0.02 50) !important;
}

.arco-upload-trigger {
  background: oklch(0.98 0.01 95) !important;
  border-color: oklch(0.85 0.01 60 / 0.3) !important;
}

/* 空状态 */
.arco-empty {
  color: oklch(0.50 0.02 50) !important;
}

/* 结果组件 */
.arco-result-title {
  color: oklch(0.20 0.02 50) !important;
}

.arco-result-subtitle {
  color: oklch(0.40 0.02 50) !important;
}

/* 卡片 */
.arco-card {
  background: oklch(0.98 0.01 95) !important;
  border-color: oklch(0.85 0.01 60 / 0.2) !important;
}

.arco-card-header-title {
  color: oklch(0.20 0.02 50) !important;
}

/* 头像 */
.arco-avatar {
  background: oklch(0.50 0.16 45 / 0.2) !important;
  color: oklch(0.40 0.10 45) !important;
}

/* 滚动条 */
::-webkit-scrollbar {
  width: 6px;
  height: 6px;
}

::-webkit-scrollbar-track {
  background: transparent;
}

::-webkit-scrollbar-thumb {
  background: oklch(0.85 0.01 60 / 0.3);
  border-radius: 3px;
}

::-webkit-scrollbar-thumb:hover {
  background: oklch(0.50 0.16 45 / 0.4);
}
</style>
