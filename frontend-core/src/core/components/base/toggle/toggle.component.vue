<template>
    <label class="inline-flex items-center gap-3 select-none" :class="{ 'opacity-50 cursor-not-allowed': disabled }">
        <span v-if="$slots.label" class="text-sm font-medium text-neutral-900">
            <slot name="label" />
        </span>

        <input type="checkbox" class="sr-only" :checked="modelValue" :disabled="disabled" role="switch"
            :aria-checked="modelValue" @change="onChange" />

        <span
            class="relative inline-flex h-6 w-11 cursor-pointer items-center rounded-full transition-colors duration-200"
            :class="[
                modelValue ? 'bg-primary-100' : 'bg-neutral-300',
                disabled ? 'cursor-not-allowed' : 'cursor-pointer'
            ]">
            <span class="inline-block h-5 w-5 transform rounded-full bg-white shadow transition-transform duration-200"
                :class="modelValue ? 'translate-x-5' : 'translate-x-1'" />
        </span>

        <span v-if="$slots.description" class="text-sm text-neutral-500">
            <slot name="description" />
        </span>
    </label>
</template>


<script setup lang="ts">
const props = defineProps({
    disabled: {
        type: Boolean,
        default: false,
    },
})

const modelValue = defineModel<boolean>()

const emit = defineEmits<{
    (e: 'update:modelValue', value: boolean): void
}>()

const onChange = (e: Event) => {
    if (props.disabled) return
    const target = e.target as HTMLInputElement
    modelValue.value = target.checked
    emit('update:modelValue', target.checked)
}
</script>


<style scoped>
/* small helper: ensure button has no native border */
button[role="switch"] {
    border: 0;
}
</style>
