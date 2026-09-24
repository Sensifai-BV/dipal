<template>
  <div>
    <div class="flex flex-row justify-center gap-4">
      <img
        v-for="logo in companyLogos"
        :key="logo.id"
        :src="logo.src"
        alt="Company Logo"
        class="w-20 h-auto"
      />
    </div>
  </div>
</template>
<script setup lang="ts">
import europeLogo from "@/assets/svgs/europe.svg";
import sesifiLogo from "@/assets/svgs/sesifi.svg";
import spadeLogo from "@/assets/svgs/spade.svg";
const companyLogos = [
  {
    id: 1,
    src: spadeLogo,
  },
  {
    id: 2,
    src: europeLogo,
  },
  {
    id: 3,
    src: sesifiLogo,
  },
];
</script>
