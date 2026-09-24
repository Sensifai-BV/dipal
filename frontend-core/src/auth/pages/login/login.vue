<template>
  <div class="bg-white rounded-lg">
    <base-form @submit="submitForm" @validation="handleValidation">
      <div class="flex flex-col gap-6">
        <base-input
          v-model="userCredentials.email"
          name="email"
          label="Email"
          type="email"
          placeholder="Enter your email"
          :rules="[
            required('Email is required'),
            email('Please enter a valid email address'),
          ]"
        />
        <base-input
          v-model="userCredentials.password"
          name="password"
          label="Password"
          :type="showPassword ? 'text' : 'password'"
          placeholder="Enter your password"
          :rules="[required('Password is required')]"
        >
          <template #suffix>
            <base-icon
              :name="showPassword ? 'Eye' : 'EyeOff'"
              :size="20"
              color="#9CA3AF"
              :stroke-width="1.5"
              default-class="inline-block cursor-pointer"
              @click="togglePasswordVisibility"
            />
          </template>
        </base-input>
        <div class="flex flex-col text-center gap-6">
          <base-button
            type="submit"
            variant="primary"
            :loading="loading"
            :disabled="!isFormValid"
            block
          >
            Sign In
          </base-button>
          <router-link :to="AuthRoute.REGISTER">
            <span class="text-primary text-md"> Press here to register </span>
          </router-link>
        </div>
      </div>
    </base-form>
  </div>
</template>

<script setup lang="ts">
import { AuthRoute } from "@/auth/router/route.constant";
import { useUserStore } from "@/auth/store/user.store";
import { DASHBOARD_ROUTES } from "@/module/dashboard/router/router.constant";
import {
  baseButton,
  baseForm,
  baseIcon,
  baseInput,
} from "@core/components/base/index";
import { email, required } from "@core/utils/validation";
import { reactive, ref } from "vue";
import { useRouter } from "vue-router";

const router = useRouter();
const userStore = useUserStore();
const loading = ref<boolean>(false);
const isFormValid = ref<boolean>(false);
const userCredentials = reactive({
  email: "",
  password: "",
});

const showPassword = ref<boolean>(false);
const togglePasswordVisibility = () => {
  showPassword.value = !showPassword.value;
};

const handleValidation = (valid: boolean) => {
  isFormValid.value = valid;
};

const submitForm = async () => {
  if (!isFormValid.value) return;

  try {
    loading.value = true;
    await userStore.login(userCredentials);
    
    router.push(DASHBOARD_ROUTES.dashboard);
  } catch (error) {
    console.error("Login failed:", error);
  } finally {
    loading.value = false;
  }
};
</script>
