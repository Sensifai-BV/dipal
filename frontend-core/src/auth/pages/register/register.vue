<template>
  <div class="bg-white rounded-lg">
    <base-form @submit="handleFormSubmit" @validation="handleValidation">
      <div class="flex flex-col gap-5">
        <base-input
          v-model="formData.fullName"
          name="fullName"
          label="Full Name *"
          type="text"
          placeholder="John Doe"
          :rules="[
            required('Full name is required'),
            minLength(2, 'Full name must be at least 2 characters'),
          ]"
        />
        <!-- 
        <base-input
          v-model="formData.family"
          name="family"
          label="Family *"
          type="text"
          placeholder="Doe"
          :rules="[
            required('Family name is required'),
            minLength(2, 'Family name must be at least 2 characters'),
          ]"
        /> -->

        <base-input
          v-model="formData.email"
          name="email"
          label="Email *"
          type="email"
          placeholder="your.email@example.com"
          :rules="[
            required('Email is required'),
            email('Please enter a valid email address'),
          ]"
        />
        <!-- 
        <base-drop-down
          v-model="formData.role"
          name="role"
          label="Role *"
          :options="ROLE_OPTIONS"
          placeholder="Select your role"
          :rules="[required('Role is required')]"
        /> -->

        <!-- <base-input
          v-model="formData.organization"
          name="organization"
          label="Organization *"
          type="text"
          placeholder="Your Organization"
          :rules="[
            required('Organization  is required'),
            minLength(2, 'Organization  must be at least 2 characters'),
          ]"
        /> -->

        <base-input
          v-model="formData.password"
          name="password"
          label="Password *"
          :type="showPassword ? 'text' : 'password'"
          placeholder="••••••••"
          :rules="[
            required('Password is required'),
            minLength(8, 'Password must be at least 8 characters'),
          ]"
        >
          <template #suffix>
            <base-icon
              :name="showPassword ? 'Eye' : 'EyeOff'"
              :size="16"
              color="#6A7282"
              :stroke-width="2"
              default-class="cursor-pointer"
              @click="togglePasswordVisibility"
            />
          </template>
        </base-input>

        <base-input
          v-model="formData.confirmPassword"
          name="confirmPassword"
          label="Confirm Password *"
          :type="showConfirmPassword ? 'text' : 'password'"
          placeholder="••••••••"
          :rules="[
            required('Please confirm your password'),
            matchField(() => formData.password, 'Passwords do not match'),
          ]"
        >
          <template #suffix>
            <base-icon
              :name="showConfirmPassword ? 'Eye' : 'EyeOff'"
              :size="16"
              color="#6A7282"
              :stroke-width="2"
              default-class="cursor-pointer"
              @click="toggleConfirmPasswordVisibility"
            />
          </template>
        </base-input>

        <span
          class="border border-blue-100 rounded-md px-3 py-3 text-xs text-neutral-900 bg-soft-white"
        >
          By registering, you agree to PhotoGear's Terms of Service and Privacy
          Policy.
        </span>

        <base-button
          type="submit"
          variant="primary"
          block
          class="mt-2"
          :disabled="loading"
        >
          Create Account
        </base-button>

        <div class="text-center">
          <router-link :to="AuthRoute.LOGIN" class="text-primary text-base">
            Already have an account? Sign in
          </router-link>
        </div>
      </div>
    </base-form>
  </div>
</template>

<script setup lang="ts">
import { AuthRoute } from "@/auth/router/route.constant";
import { useUserStore } from "@/auth/store/user.store";
import {
  baseButton,
  baseForm,
  baseIcon,
  baseInput,
} from "@core/components/base/index";
import { email, matchField, minLength, required } from "@core/utils/validation";
import { reactive, ref } from "vue";
import { useRouter } from "vue-router";
import { ROLE_OPTIONS } from "./register.constant";

const formData = reactive({
  fullName: "",
  // organization: "",
  email: "",
  password: "",
  confirmPassword: "",
  // role: "",
});

const router = useRouter();
const userStore = useUserStore();
const showPassword = ref<boolean>(false);
const showConfirmPassword = ref<boolean>(false);
const isFormValid = ref<boolean>(false);
const loading = ref<boolean>(false);

const togglePasswordVisibility = () => {
  showPassword.value = !showPassword.value;
};

const toggleConfirmPasswordVisibility = () => {
  showConfirmPassword.value = !showConfirmPassword.value;
};

const handleValidation = (valid: boolean) => {
  isFormValid.value = valid;
};

const handleFormSubmit = async (data: Record<string, any>) => {
  try {
    loading.value = true;
    // isFormValid.value = true;
    await userStore.register({
      full_name: data.fullName,
      email: data.email,
      password: data.password,
      role: Number(ROLE_OPTIONS[1]?.value),
      organization: data.email,
      confirm_password: data.confirmPassword,
    });
    router.push(AuthRoute.LOGIN);
  } catch (error) {
    // isFormValid.value = false;
    console.error("Registration failed:", error);
  } finally {
    loading.value = false;
  }
};
</script>
