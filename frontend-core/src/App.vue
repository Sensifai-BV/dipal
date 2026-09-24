<template>
  <component :is="layout">
    <router-view />
  </component>
  <ToastContainer />
</template>

<script setup lang="ts">
import { computed, defineAsyncComponent } from "vue";
import { useRoute } from "vue-router";

const route = useRoute();

const layout = computed(() => {
  const layoutName = route.meta.layout as string | undefined;

  if (!layoutName) {
    return { template: "<router-view />" };
  }

  const moduleRoute = () => import(`@/module/layouts/${layoutName}-layout.vue`);
  const authRoute = () => import(`@/auth/layout/${layoutName}-layout.vue`);

  const currentRoute = layoutName === "auth" ? authRoute : moduleRoute;

  return defineAsyncComponent(currentRoute);
});
</script>
