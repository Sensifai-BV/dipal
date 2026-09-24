<template>
  <div class="min-h-screen bg-white flex flex-col items-center justify-center py-12 px-4 sm:px-6 lg:px-8">
    <div class="w-full" style="max-width: 448px">
      <div class="flex flex-col items-center gap-24 mb-24">
        <div class="flex items-center gap-2">
          <img :src="logo" alt="PhotoGear" class="h-7 w-7" />
          <h1 class="text-[28px] font-sen font-bold leading-7 tracking-tight text-primary-200">
            PhotoGear
          </h1>
        </div>

        <p class="text-base font-sans text-secondary text-center leading-6">
          {{ pageTitle }}
        </p>
      </div>

      <!-- Auth Content -->
      <div class="bg-white rounded-lg">
        <RouterView />
      </div>
    </div>

    <div class="flex flex-row justify-center gap-7 fixed bottom-9">
      <img v-for="logo in CompanyLogos" :key="logo.id" :src="logo.src" alt="Company Logo" class="w-28 h-auto" />
    </div>
  </div>
</template>

<script setup lang="ts">
import logo from "@/assets/svgs/logo.svg";
import { CompanyLogos } from "@/core/utils/global.constant";
import { computed } from "vue";
import { RouterView, useRoute } from "vue-router";

const route = useRoute();

const pageTitle = computed(() => {
  if (route.name === "auth-register") {
    return "Create Your PhotoGear Account";
  } else if (route.name === "auth-login") {
    return "Cloud-Native Photogrammetric Processing Platform";
  }
  return "Welcome to PhotoGear";
});
</script>
