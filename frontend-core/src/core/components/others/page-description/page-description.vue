<template>
  <div class="flex flex-col">
    <h1 class="text-2xl text-neutral-950 font-normal">
      {{ headerData.title }}
    </h1>
    <span class="text-base text-secondary font-normal">{{
      headerData.description
    }}</span>
  </div>
</template>
<script setup lang="ts">
import { ref } from "vue";
import { useRoute } from "vue-router";

const route = useRoute();
const headerData = ref({
  title: route.meta.title || "Dashboard",
  description:
    route.meta.description || "Overview of your application statistics",
});
</script>
