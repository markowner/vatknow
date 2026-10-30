<script setup lang="ts">
import { NConfigProvider, NDialogProvider, NGlobalStyle, NLoadingBarProvider, NMessageProvider, NNotificationProvider, dateZhCN, zhCN } from "naive-ui";
import type { GlobalThemeOverrides } from "naive-ui";

const themeOverrides: GlobalThemeOverrides = {
  common: {
    primaryColor: "#2563eb",
    primaryColorHover: "#1d4ed8",
    primaryColorPressed: "#1e40af",
    primaryColorSuppl: "#3b82f6",
    successColor: "#059669",
    warningColor: "#d97706",
    errorColor: "#dc2626",
    infoColor: "#2563eb",
    borderRadius: "10px",
    borderRadiusSmall: "6px",
    fontFamily:
      'ui-sans-serif, system-ui, -apple-system, "Segoe UI", "PingFang SC", "Hiragino Sans GB", "Noto Sans SC", sans-serif',
    fontSize: "14px",
    bodyColor: "#f6f7f9",
    cardColor: "#ffffff",
    modalColor: "#ffffff",
    popoverColor: "#ffffff",
    tableColor: "#ffffff",
    inputColor: "#ffffff",
    tagColor: "#f2f4f7",
    borderColor: "#e8eaee",
    dividerColor: "#eef0f3",
    textColorBase: "#0d1117",
    textColor1: "rgb(13, 17, 23)",
    textColor2: "rgb(52, 64, 84)",
    textColor3: "rgb(102, 112, 133)",
    placeholderColor: "#98a2b3",
    hoverColor: "rgba(16, 24, 40, 0.04)",
    pressedColor: "rgba(16, 24, 40, 0.06)",
  },
  Layout: {
    siderColor: "#ffffff",
    siderBorderColor: "#eceef2",
    headerColor: "#ffffff",
    headerBorderColor: "#eceef2",
    color: "#f6f7f9",
  },
  Menu: {
    itemHeight: "36px",
    borderRadius: "8px",
    itemTextColor: "#475467",
    itemTextColorHover: "#0d1117",
    itemTextColorActive: "#1d4ed8",
    itemTextColorChildActive: "#1d4ed8",
    itemIconColor: "#98a2b3",
    itemIconColorHover: "#475467",
    itemIconColorActive: "#2563eb",
    itemColorActive: "#f0f5ff",
    itemColorHover: "#f5f6f8",
  },
  Card: {
    borderRadius: "14px",
    paddingMedium: "20px 22px",
    borderColor: "#e8eaee",
    color: "#ffffff",
  },
  Button: {
    borderRadiusMedium: "8px",
    borderRadiusSmall: "6px",
    fontWeightStrong: "600",
  },
  Tag: {
    borderRadius: "6px",
  },
  Input: {
    borderRadius: "8px",
  },
  Tabs: {
    tabFontWeightActive: "600",
  },
};
</script>

<template>
  <n-config-provider :theme-overrides="themeOverrides" :locale="zhCN" :date-locale="dateZhCN">
    <n-global-style />
    <n-loading-bar-provider>
      <n-dialog-provider>
        <n-notification-provider>
          <n-message-provider>
            <router-view />
          </n-message-provider>
        </n-notification-provider>
      </n-dialog-provider>
    </n-loading-bar-provider>
  </n-config-provider>
</template>
