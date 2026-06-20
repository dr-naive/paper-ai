<template>
  <a-config-provider :locale="zhCN">
    <router-view />
  </a-config-provider>
</template>

<script setup lang="ts">
import zhCN from '@arco-design/web-vue/es/locale/lang/zh-cn'
</script>

<style>
* { margin: 0; padding: 0; box-sizing: border-box; }
html, body, #app {
  width: 100%;
  min-height: 100%;
  color-scheme: light;
}
body {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
  color: #1d2129;
  background: #f5f7fa;
}

/* ===== 全局 Arco 浅色主题 ===== */

/* 按钮 */
.arco-btn-primary {
  background: linear-gradient(135deg, #6366f1, #8b5cf6) !important;
  border-color: #6366f1 !important;
}

.arco-btn-primary:hover {
  background: linear-gradient(135deg, #5558e6, #7c4feb) !important;
}

/* 输入框 */
.arco-input-wrapper,
.arco-input-password {
  background: #fff !important;
  border-color: #e5e6eb !important;
  color: #1d2129 !important;
}

.arco-input-wrapper:hover,
.arco-input-password:hover {
  border-color: #6366f1 !important;
}

.arco-input-wrapper:focus-within,
.arco-input-password:focus-within {
  border-color: #6366f1 !important;
  box-shadow: 0 0 0 2px rgba(99, 102, 241, 0.15) !important;
}

.arco-input {
  color: #1d2129 !important;
}

.arco-input::placeholder {
  color: #a9aeb8 !important;
}

/* 表单标签 */
.arco-form-item-label {
  color: #4e5969 !important;
}

/* 链接 */
.arco-link {
  color: #6366f1 !important;
}

.arco-link:hover {
  color: #4f46e5 !important;
}

/* 列表 */
.arco-list-item {
  border-bottom-color: #e5e6eb !important;
}

.arco-list-item-meta-title {
  color: #1d2129 !important;
}

.arco-list-item-meta-description {
  color: #86909c !important;
}

/* 标签 */
.arco-tag {
  color: #6366f1 !important;
  background: rgba(99, 102, 241, 0.08) !important;
  border-color: rgba(99, 102, 241, 0.15) !important;
}

/* 下拉菜单 */
.arco-dropdown-menu {
  background: #fff !important;
  border-color: #e5e6eb !important;
}

.arco-dropdown-option {
  color: #1d2129 !important;
}

.arco-dropdown-option:hover {
  background: rgba(99, 102, 241, 0.06) !important;
}

/* 模态框 */
.arco-modal {
  background: #fff !important;
  border-color: transparent !important;
}

.arco-modal-title {
  color: #1d2129 !important;
}

.arco-modal-header {
  border-bottom-color: #e5e6eb !important;
}

/* Tabs */
.arco-tabs-header {
  border-bottom-color: #e5e6eb !important;
}

.arco-tabs-tab {
  color: #86909c !important;
}

.arco-tabs-tab-active {
  color: #6366f1 !important;
}

.arco-tabs-tab:hover {
  color: #6366f1 !important;
}

/* 选择器 */
.arco-select-view {
  background: #fff !important;
  border-color: #e5e6eb !important;
  color: #1d2129 !important;
}

.arco-select-view:hover {
  border-color: #6366f1 !important;
}

.arco-select-dropdown {
  background: #fff !important;
  border-color: #e5e6eb !important;
}

.arco-select-option {
  color: #1d2129 !important;
}

.arco-select-option:hover {
  background: rgba(99, 102, 241, 0.06) !important;
}

/* 单选按钮组 */
.arco-radio-group-button .arco-radio-button {
  background: #fff !important;
  border-color: #e5e6eb !important;
  color: #4e5969 !important;
}

.arco-radio-group-button .arco-radio-button-checked {
  background: #6366f1 !important;
  border-color: #6366f1 !important;
  color: white !important;
}

/* 上传组件 */
.arco-upload {
  color: #4e5969 !important;
}

/* 空状态 */
.arco-empty {
  color: #86909c !important;
}

/* 结果组件 */
.arco-result-title {
  color: #1d2129 !important;
}

.arco-result-subtitle {
  color: #86909c !important;
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
  background: rgba(0, 0, 0, 0.12);
  border-radius: 3px;
}

::-webkit-scrollbar-thumb:hover {
  background: rgba(0, 0, 0, 0.2);
}
</style>
