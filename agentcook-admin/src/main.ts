import { createApp } from "vue";
import { createPinia } from "pinia";
import ElementPlus from "element-plus";
import * as ElementPlusIcons from "@element-plus/icons-vue";
import "element-plus/dist/index.css";
import "element-plus/theme-chalk/dark/css-vars.css";
import "@agentcook-cc/design-tokens/dist/css/variables.css";
import App from "./App.vue";
import router from "./router";

const app = createApp(App);
app.use(createPinia());
app.use(router);
app.use(ElementPlus);

for (const [name, component] of Object.entries(ElementPlusIcons)) {
  app.component(name, component);
}

app.config.errorHandler = (error, instance, info) => {
  console.error("[Vue ErrorHandler]", error, "\nComponent:", instance, "\nInfo:", info);
  import("element-plus").then(({ ElNotification }) => {
    ElNotification({
      title: "Unexpected Error",
      message: error instanceof Error ? error.message : "An unexpected error occurred.",
      type: "error",
      duration: 8000,
    });
  });
};

app.config.warnHandler = (msg, instance, trace) => {
  console.warn("[Vue Warning]", msg, "\nTrace:", trace);
};

app.mount("#app");
