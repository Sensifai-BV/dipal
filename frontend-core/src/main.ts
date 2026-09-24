import { createPinia } from "pinia";
import piniaPluginPersistedstate from "pinia-plugin-persistedstate";

import { createApp } from "vue";
import App from "./App.vue";
import { vFormatDate } from "./core/directives";
import { toastPlugin } from "./core/plugins/toast.plugin";
import { router } from "./router";
import "./style.css";

import VCalendar from "v-calendar";
import "v-calendar/style.css";

const app = createApp(App);
const pinia = createPinia();

app.use(VCalendar, {});

app.use(pinia);
pinia.use(piniaPluginPersistedstate);

app.use(router);
app.use(toastPlugin);

// Register global directives
app.directive("format-date", vFormatDate);

app.mount("#app");
