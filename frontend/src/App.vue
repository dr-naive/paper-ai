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
  --pa-primary: #B13A17;
  --pa-primary-hover: #942F13;
  --pa-primary-soft: #FFF0E9;

  --pa-ink: #202124;
  --pa-text: #3F4246;
  --pa-muted: #71757A;

  --pa-bg: #F7F7F5;
  --pa-surface: #FFFFFF;
  --pa-surface-soft: #F2F2EF;
  --pa-border: #E2E3DF;
  --pa-border-strong: #D3D5D0;

  --pa-info: #3568A8;
  --pa-info-soft: #EEF4FB;
  --pa-success: #2D7A50;
  --pa-success-soft: #EDF7F0;
  --pa-warning: #9A6413;
  --pa-warning-soft: #FFF6E4;
  --pa-danger: #B43C36;
  --pa-danger-soft: #FFF0EF;

  --pa-focus-ring: 0 0 0 3px rgb(177 58 23 / 0.18);
  --pa-shadow-sm: 0 1px 2px rgb(20 24 28 / 0.06), 0 2px 6px rgb(20 24 28 / 0.04);
  --pa-shadow-md: 0 10px 30px rgb(20 24 28 / 0.10);

  --pa-radius-sm: 6px;
  --pa-radius-md: 8px;
  --pa-radius-lg: 12px;

  --pa-space-1: 4px;
  --pa-space-2: 8px;
  --pa-space-3: 12px;
  --pa-space-4: 16px;
  --pa-space-5: 20px;
  --pa-space-6: 24px;
  --pa-space-8: 32px;

  --pa-sidebar-width: 208px;
  --pa-sidebar-collapsed-width: 60px;
  --pa-header-height: 56px;
  --pa-content-max: 1280px;
  --pa-editor-reading-width: 820px;

  /* Protected PDF reader surfaces use a separate dark neutral scale. */
  --pa-reader-toolbar: #262A2E;
  --pa-reader-toolbar-control: #3A4148;
}

*,
*::before,
*::after {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

html, body, #app {
  width: 100%;
  min-height: 100%;
  color-scheme: light;
}

body {
  font-family: Inter, ui-sans-serif, -apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC", "Hiragino Sans GB", "Microsoft YaHei", Arial, sans-serif;
  color: var(--pa-text);
  background: var(--pa-bg);
  font-size: 14px;
  line-height: 1.5;
  -webkit-font-smoothing: antialiased;
  text-rendering: optimizeLegibility;
}

button,
input,
textarea,
select {
  font: inherit;
}

a {
  color: var(--pa-primary);
}

h1,
h2,
h3,
h4,
h5,
h6 {
  color: var(--pa-ink);
  text-wrap: balance;
}

:focus-visible {
  outline: 2px solid var(--pa-primary);
  outline-offset: 2px;
}

::selection {
  color: var(--pa-ink);
  background: var(--pa-primary-soft);
}

.pa-form-error {
  margin: -4px 0 18px;
  padding: 10px 12px;
  border: 1px solid var(--pa-danger);
  border-radius: var(--pa-radius-md);
  color: var(--pa-danger);
  background: var(--pa-danger-soft);
  font-size: 13px;
  line-height: 1.5;
}

.pa-sr-only {
  position: absolute !important;
  width: 1px !important;
  height: 1px !important;
  padding: 0 !important;
  margin: -1px !important;
  overflow: hidden !important;
  clip: rect(0, 0, 0, 0) !important;
  white-space: nowrap !important;
  border: 0 !important;
}

/* ===== Arco 全局控件基础样式 ===== */

.arco-btn-primary {
  background: var(--pa-primary) !important;
  border-color: var(--pa-primary) !important;
  color: var(--pa-surface) !important;
  transition: background-color 180ms ease, border-color 180ms ease, box-shadow 180ms ease !important;
}

.arco-btn-primary:not(.arco-btn-disabled):hover {
  background: var(--pa-primary-hover) !important;
  border-color: var(--pa-primary-hover) !important;
  box-shadow: var(--pa-shadow-sm);
}

.arco-btn-secondary {
  background: var(--pa-surface-soft) !important;
  border-color: var(--pa-border) !important;
  color: var(--pa-text) !important;
  transition: background-color 180ms ease, border-color 180ms ease, box-shadow 180ms ease !important;
}

.arco-btn-secondary:not(.arco-btn-disabled):hover {
  background: var(--pa-surface) !important;
  border-color: var(--pa-border-strong) !important;
  box-shadow: var(--pa-shadow-sm);
}

.arco-btn-primary:focus-visible,
.arco-btn-secondary:focus-visible {
  box-shadow: var(--pa-focus-ring);
}

.arco-btn-primary.arco-btn-disabled,
.arco-btn-secondary.arco-btn-disabled {
  box-shadow: none !important;
  cursor: not-allowed;
}

.arco-btn-text {
  color: var(--pa-muted) !important;
}

.arco-btn-text:hover {
  color: var(--pa-primary-hover) !important;
  background: var(--pa-primary-soft) !important;
}

.arco-input-wrapper,
.arco-input-password {
  background: var(--pa-surface) !important;
  border-color: var(--pa-border) !important;
  color: var(--pa-text) !important;
}

.arco-input-wrapper:hover,
.arco-input-password:hover {
  border-color: var(--pa-border-strong) !important;
}

.arco-input-wrapper:focus-within,
.arco-input-password:focus-within {
  border-color: var(--pa-primary) !important;
  box-shadow: var(--pa-focus-ring) !important;
}

.arco-input {
  color: var(--pa-text) !important;
}

.arco-input::placeholder {
  color: var(--pa-muted) !important;
}

.arco-textarea-wrapper {
  background: var(--pa-surface) !important;
  border-color: var(--pa-border) !important;
}

.arco-textarea-wrapper:hover {
  border-color: var(--pa-border-strong) !important;
}

.arco-textarea-wrapper:focus-within,
.arco-textarea-wrapper.arco-textarea-focus {
  border-color: var(--pa-primary) !important;
  box-shadow: var(--pa-focus-ring) !important;
}

.arco-textarea {
  color: var(--pa-text) !important;
}

.arco-textarea::placeholder {
  color: var(--pa-muted) !important;
}

.arco-textarea-wrapper.arco-textarea-disabled {
  background: var(--pa-surface-soft) !important;
  color: var(--pa-muted) !important;
}

.arco-form-item-label {
  color: var(--pa-text) !important;
}

.arco-form-item-message {
  color: var(--pa-danger) !important;
}

.arco-link {
  color: var(--pa-primary) !important;
}

.arco-link:hover {
  color: var(--pa-primary-hover) !important;
}

.arco-list-item {
  border-bottom-color: var(--pa-border) !important;
}

.arco-list-item-meta-title {
  color: var(--pa-ink) !important;
}

.arco-list-item-meta-description {
  color: var(--pa-muted) !important;
}

.arco-dropdown-menu {
  background: var(--pa-surface) !important;
  border-color: var(--pa-border) !important;
  box-shadow: var(--pa-shadow-md) !important;
}

.arco-dropdown-option {
  color: var(--pa-text) !important;
}

.arco-dropdown-option:hover {
  background: var(--pa-primary-soft) !important;
}

.arco-modal {
  background: var(--pa-surface) !important;
  border-color: var(--pa-border) !important;
  border-radius: var(--pa-radius-lg);
  box-shadow: var(--pa-shadow-md);
}

.arco-modal-title {
  color: var(--pa-ink) !important;
}

.arco-modal-header {
  border-bottom-color: var(--pa-border) !important;
}

.arco-modal-body {
  color: var(--pa-text) !important;
}

.arco-drawer {
  background: var(--pa-surface) !important;
  color: var(--pa-text) !important;
}

.arco-drawer-header {
  border-bottom-color: var(--pa-border) !important;
}

.arco-drawer-title {
  color: var(--pa-ink) !important;
}

.arco-drawer-body {
  color: var(--pa-text) !important;
}

.arco-popover-popup-content,
.arco-tooltip-content {
  border-color: var(--pa-border) !important;
  background: var(--pa-surface) !important;
  color: var(--pa-text) !important;
  box-shadow: var(--pa-shadow-md) !important;
}

.arco-tabs-header {
  border-bottom-color: var(--pa-border) !important;
}

.arco-tabs-tab {
  color: var(--pa-muted) !important;
}

.arco-tabs-tab-active {
  color: var(--pa-primary) !important;
}

.arco-tabs-tab:hover {
  color: var(--pa-primary-hover) !important;
}

.arco-select-view {
  background: var(--pa-surface) !important;
  border-color: var(--pa-border) !important;
  color: var(--pa-text) !important;
}

.arco-select-view:hover {
  border-color: var(--pa-border-strong) !important;
}

.arco-select-dropdown {
  background: var(--pa-surface) !important;
  border-color: var(--pa-border) !important;
  box-shadow: var(--pa-shadow-md) !important;
}

.arco-select-option {
  color: var(--pa-text) !important;
}

.arco-select-option:hover {
  background: var(--pa-primary-soft) !important;
}

.arco-radio-group-button .arco-radio-button {
  background: var(--pa-surface-soft) !important;
  border-color: var(--pa-border) !important;
  color: var(--pa-text) !important;
}

.arco-radio-group-button .arco-radio-button-checked {
  background: var(--pa-primary) !important;
  border-color: var(--pa-primary) !important;
  color: var(--pa-surface) !important;
}

.arco-switch-checked {
  background: var(--pa-primary) !important;
}

.arco-upload {
  color: var(--pa-text) !important;
}

.arco-upload-trigger {
  background: var(--pa-surface) !important;
  border-color: var(--pa-border) !important;
}

.arco-empty {
  color: var(--pa-muted) !important;
}

.arco-result-title {
  color: var(--pa-ink) !important;
}

.arco-result-subtitle {
  color: var(--pa-muted) !important;
}

.arco-card {
  background: var(--pa-surface) !important;
  border-color: var(--pa-border) !important;
  border-radius: var(--pa-radius-md);
  box-shadow: none !important;
}

.arco-card-header-title {
  color: var(--pa-ink) !important;
}

.arco-avatar {
  background: var(--pa-primary-soft) !important;
  color: var(--pa-primary-hover) !important;
}

::-webkit-scrollbar {
  width: 6px;
  height: 6px;
}

::-webkit-scrollbar-track {
  background: transparent;
}

::-webkit-scrollbar-thumb {
  background: var(--pa-border-strong);
  border-radius: var(--pa-radius-sm);
}

::-webkit-scrollbar-thumb:hover {
  background: var(--pa-muted);
}

@media (prefers-reduced-motion: reduce) {
  .arco-btn-primary,
  .arco-btn-secondary {
    transition: none !important;
  }
}
</style>
