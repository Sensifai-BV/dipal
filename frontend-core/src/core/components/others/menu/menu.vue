<template>
  <div
    class="bg-white border-r border-gray-200 flex flex-col h-full w-70 relative"
  >
    <div
      class="flex flex-col text-left border-b border-gray-200 py-6 shrink-0 px-16"
    >
      <div class="flex flex-row gap-1.5 items-center">
        <img :src="logo" alt="Logo" class="w-25 h-auto" />
        <h2 class="text-xl font-bold font-sen text-primary-200">PhotoGear</h2>
      </div>
      <span class="text-secondary">Admin Dashboard</span>
    </div>

    <div class="flex flex-col justify-between h-full p-16">
      <nav class="flex flex-col h-full">
        <button
          v-for="item in props.items"
          :key="item.route"
          :disabled="item.disabled"
          @click="handleNavigate(item.route)"
          :class="[navItemClass(item)]"
        >
          <baseIcon
            :name="item.icon"
            :size="20"
            :color="route.path === item.route || route.path.startsWith(item.route + '/') ? '#1447e6' : '#4a5565'"
            :stroke-width="2"
          />
          <span class="font-sans text-base leading-normal">
            {{ item.label }}
          </span>
        </button>
      </nav>

      <div class="flex flex-col justify-end h-full">
        <div>
          <div class="flex flex-row justify-center gap-4">
            <img
              v-for="logo in CompanyLogos"
              :key="logo.id"
              :src="logo.src"
              alt="Company Logo"
              class="w-20 h-auto"
            />
          </div>
        </div>

        <div class="border-b border-gray-200 my-3.5"></div>

        <div class="flex flex-col gap-3">
          <div class="flex items-center gap-3">
            <div
              class="bg-blue-100 rounded-full flex items-center justify-center w-10 h-10 shrink-0"
            >
              <p
                class="font-sans text-base leading-normal text-primary-100 font-normal"
              >
                {{ user?.first_name.charAt(0) }}{{ user?.last_name.charAt(0) }}
              </p>
            </div>
            <div class="flex-1 flex flex-col">
              <p class="font-sans text-base leading-normal text-neutral-950">
                {{ user?.first_name }} {{ user?.last_name }}
              </p>
              <p
                class="font-sans text-base leading-normal text-secondary overflow-hidden text-ellipsis whitespace-nowrap"
              >
                {{ user?.email }}
              </p>
            </div>
          </div>

          <button
            @click="handleSignOut"
            class="cursor-pointer border border-border h-9 rounded flex items-center gap-3 px-[13px] hover:bg-neutral-100 transition-colors w-full"
          >
            <baseIcon
              name="LogOut"
              :size="16"
              color="#101828"
              :stroke-width="2"
            />
            <span class="font-sans text-sm leading-base text-neutral-950">
              Sign Out
            </span>
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import logo from "@/assets/svgs/logo.svg";
import { baseIcon } from "@core/components/base/index";
import { useRoute, useRouter } from "vue-router";
import type { MenuEmits, MenuItem, MenuProps } from "./menu.type";
import { CompanyLogos } from "@/core/utils/global.constant";

const route = useRoute();
const router = useRouter();

const props = defineProps<MenuProps>();
const emit = defineEmits<MenuEmits>();


const handleNavigate = (route: string) => {
  router.push(route);
};

function navItemClass(item: MenuItem) {
  const base =
    "flex items-center gap-2 h-14 rounded-md transition-colors text-base px-2 cursor-pointer";

  const active =
    route.path === item.route || route.path.startsWith(item.route + "/")
      ? "bg-blue-50 text-primary-100"
      : "text-neutral-900 hover:bg-neutral-100";

  const disabled = item.disabled ? "!cursor-not-allowed opacity-50" : "";

  return [base, active, disabled];
}


const handleSignOut = () => {
  emit("signOut");
};
</script>
