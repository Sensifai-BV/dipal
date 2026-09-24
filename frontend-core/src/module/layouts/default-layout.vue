<template>
  <div class="flex flex-row h-svh w-full">
    <base-menu :items="MENU_ROUTES" @sign-out="signOut" :user="user" />
    <div class="p-32 w-full overflow-y-auto bg-neutral-200">
      <router-view />
    </div>
  </div>
</template>
<script setup lang="ts">
import { AuthRoute } from "@/auth/router/route.constant";
import { BaseMenu, type UserInfo } from "@core/components/others/index";
import { onMounted, ref } from "vue";
import { fecthUserInfo } from "../service/module.service";
import { MENU_ROUTES } from "./default-layout.constant";
import { useRouter } from "vue-router";

const router = useRouter();

const signOut = () => {
  console.log("Sign out triggered");
  localStorage.clear();
  
  router.push(AuthRoute.LOGIN);
};

const user = ref<UserInfo>();
onMounted(async () => {
  const userInfo = await fecthUserInfo();
  user.value = userInfo;
});
</script>
