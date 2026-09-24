# Copilot Custom Instructions — Frontend
_These guidelines apply to every suggestion Copilot makes in this repository._

---

## 1. High-level Architecture

This is the **Vue 3 + TypeScript** frontend for PhotoGear — a drone imagery processing platform.

### Tech Stack
* **Vue 3.5** with `<script setup>` and Composition API
* **TypeScript** (strict)
* **Vite 7** for build tooling
* **Tailwind CSS 4** for styling
* **Pinia 3** for state management (persisted with `pinia-plugin-persistedstate`)
* **Vue Router 4** for routing
* **Axios** for HTTP with `await-to-js` wrapper
* **lucide-vue-next** for icons

### Project Structure
```
src/
├── auth/              # Authentication pages (login, register)
│   ├── pages/
│   ├── router/
│   └── store/
├── core/              # Shared core layer
│   ├── components/    # Base + Others components
│   ├── directives/    # Custom Vue directives
│   ├── plugins/       # Vue plugins (toast, etc.)
│   ├── services/      # Axios instance, toast service
│   ├── store/         # Global stores
│   └── utils/         # Utility functions, constants
├── module/            # Feature modules
│   ├── dashboard/
│   ├── dataset/
│   ├── processing-job/
│   ├── products/
│   ├── configuration/
│   ├── layouts/
│   └── service/       # Shared module services
├── router.ts          # Root router
├── main.ts            # App entry
└── App.vue            # Root component
```

### Module Structure (each feature module)
```
module/<name>/
├── pages/<name>/
│   ├── <name>.vue          # Page component
│   ├── <name>.constant.ts  # Table headers, enums
│   └── <name>.type.ts      # TypeScript interfaces
├── router/
│   ├── router.ts           # Route definitions
│   └── route.constant.ts   # Route path constants
├── service/
│   ├── <name>.service.ts   # API service functions
│   ├── <name>.route.ts     # API endpoint constants
│   └── <name>.type.ts      # API types
└── composable/              # Module-specific composables (optional)
```

---

## 2. Coding Style

* **`<script setup lang="ts">`** for all components
* **Composition API** only — no Options API
* All props and emits must be typed with TypeScript interfaces
* Use `ref()`, `computed()`, `watch()`; avoid `reactive()` for simple values
* **No inline comments inside functions**; use JSDoc for function documentation when needed
* Use template refs with `ref<HTMLElement | null>(null)`

### Naming Conventions
* **kebab-case** for: file names, component file names, CSS classes
* **camelCase** for: variables, functions, composables
* **PascalCase** for: component imports, types, interfaces
* **SCREAMING_SNAKE_CASE** for: route constants, API route constants
* Component files: `<name>.vue`, not `<Name>.vue`

---

## 3. Component Patterns

### Base Components (`core/components/base/`)
Always use the project's base components:
* `baseTable` — Data tables with pagination, sorting, cell slots
* `baseDialog` — Modal dialogs with `#body` and `#footer` slots
* `baseButton` — Buttons with `variant`, `size`, `block`, `loading` props
* `baseInput` — Form inputs with `v-model`, `label`, `prefix`/`suffix` slots
* `baseBadge` — Status badges
* `baseIcon` — Icons via lucide-vue-next
* `baseProgressBar` — Progress indicators
* `baseDropdown` — Dropdown menus
* `baseForm` — Form wrapper
* `baseCard` — Card layout

Import from barrel: `import { baseTable, baseButton, ... } from "@/core/components/base/index";`

### Table Pattern
```vue
<base-table
  :headers="TableHeaders"
  :data="dataTableValue"
  :dataRowCount="tableProps.dataRowCount"
  :loading="tableProps.loading"
  @change="onPageChange"
>
  <template #cell-status="{ value, row }">
    <base-badge>{{ value }}</base-badge>
  </template>
  <template #cell-actions="{ row }">
    <!-- Action buttons -->
  </template>
</base-table>
```

### Dialog Pattern
```vue
<base-dialog v-model="showDialog" title="Dialog Title">
  <template #body>
    <!-- Content -->
  </template>
  <template #footer>
    <base-button variant="ghost" @click="showDialog = false">Cancel</base-button>
    <base-button variant="primary" @click="save">Save</base-button>
  </template>
</base-dialog>
```

---

## 4. API Service Pattern

* Each module has its own `service/` directory
* Use `await-to-js` (`to`) for error handling with Axios
* API routes defined in `<name>.route.ts`
* Service functions exported from `<name>.service.ts`
* Toast notifications for user feedback

```typescript
import api from "@/core/services/axios";
import to from "await-to-js";
import { toastService } from "@/core/services/toast.service";
import { API_ROUTE } from "./route";

export const getItems = async (page: number, size: number) => {
  const params = { page, page_size: size };
  const [err, res] = await to(api.get(API_ROUTE.list, { params }));
  if (err) throw err;
  return res.data;
};

export const createItem = async (payload: CreatePayload) => {
  const [err, res] = await to(api.post(API_ROUTE.create, payload));
  if (err) throw err;
  toastService.success("Created", res.data.message);
  return res.data;
};
```

### API Route Constants
```typescript
export const DATA_SET_ROUTE = {
  list: "api/uploads/list/",
  detail: "api/uploads/datasets/{dataset_id}/",
};
```

---

## 5. Routing

* Route constants in `router/route.constant.ts`
* Route definitions in `router/router.ts`
* Sidebar menu defined in `module/layouts/default-layout.constant.ts`
* All routes require `meta.requiresAuth: true` (except auth pages)
* Use named routes for `router-link :to` navigation

```typescript
export const MODULE_ROUTES = {
  list: "/module-name",
};

export const routes: RouteRecordRaw[] = [
  {
    path: MODULE_ROUTES.list,
    name: "module-name",
    component: () => import("@module/module-name/pages/module-name.vue"),
    meta: {
      title: "Module",
      description: "Module description",
      layout: "default",
      requiresAuth: true,
      role: ["admin"],
    },
  },
];
```

---

## 6. State Management

* Use **Pinia** stores in `core/store/` or module-level stores
* Stores use `defineStore` with setup syntax
* Persist with `pinia-plugin-persistedstate`

---

## 7. Styling

* **Tailwind CSS 4** utility classes only — no custom CSS unless absolutely needed
* Custom theme in `src/css/custome-theme.css`
* Standard spacing unit: multiples of 4
* Border color: `border-border`
* Rounded corners: `rounded-md`, `rounded-2xl` for cards
* Text sizes: `text-xs`, `text-sm`, `text-base`, `text-lg`
* Colors: `text-neutral-900`, `text-neutral-400`, `text-neutral-500`
* Hover states: `hover:bg-neutral-100`

### Status Badge Colors
```
processing → bg-blue-100 text-blue-800
completed  → bg-green-100 text-green-800
failed     → bg-red-100 text-red-800
pending    → bg-yellow-100 text-yellow-800
active     → bg-green-100 text-green-800
inactive   → bg-gray-100 text-gray-600
```

---

## 8. Icons

* Use `lucide-vue-next` via `baseIcon` component
* Icon names are PascalCase: `Search`, `Trash`, `Plus`, `Eye`, `Download`, `Pencil`, `Calendar`, `RotateCcw`
* Standard size: 16-18px, stroke-width: 2

```vue
<base-icon name="Search" :size="16" :stroke-width="2" />
```

---

## 9. Directives

* `v-format-date:datetime="value"` — format ISO dates

---

## 10. Backend API

* Base URL configured via environment variable
* All API paths prefixed with `api/`
* Authentication via token in Axios interceptor
* Paginated responses: `{ count, results, next, previous }`

### Key Endpoints
```
api/uploads/       — Dataset management
api/jobs/          — Processing job management
api/products/      — Product retrieval
api/fmis/webhooks/ — Webhook CRUD
health/            — System health check
```

---

## 11. Things to Avoid

* No Options API — Composition API with `<script setup>` only
* No `any` types unless unavoidable (API responses are acceptable)
* No inline styles — use Tailwind classes
* No `console.log` in production code (use `console.error` for error handlers only)
* No hardcoded API base URLs — use route constants
* No direct DOM manipulation — use refs and Vue reactivity
* No `v-html` with user input (XSS risk)
* Functions longer than 30 lines should be broken down
* No `alert()`, `confirm()`, `prompt()` — use `baseDialog` and `toastService`

---

## 12. Docker & Deployment

* `Dockerfile` for production build (nginx-based)
* `docker-compose.yml` for local development
* Build: `npm run build` (Vite)
* Dev: `npm run dev` (port 3000)

---

## 13. File Template

```vue
<template>
  <div>
    <div class="flex flex-row justify-between mb-24">
      <page-description />
    </div>

    <!-- Content -->
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from "vue";
import { baseIcon, baseButton, baseTable } from "@/core/components/base/index";
import { PageDescription } from "@/core/components/others/index";

const loading = ref(false);
const data = ref<Array<any>>([]);

const fetchData = async () => {
  loading.value = true;
  try {
    // API call
  } catch (error) {
    console.error("Error:", error);
  } finally {
    loading.value = false;
  }
};

onMounted(() => {
  fetchData();
});
</script>
```

---

**Remember:** Suggestions that violate any rule above should be suppressed or rewritten automatically.
