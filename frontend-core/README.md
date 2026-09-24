# PhotoGear - Cloud-Native Photogrammetric Processing Platform

A modern Vue 3 + TypeScript application for photogrammetric data processing with a comprehensive design system and modular architecture.

## 🚀 Tech Stack

- **Framework**: Vue 3.5+ with Composition API (`<script setup>`)
- **Language**: TypeScript 5.9+
- **Build Tool**: Vite 7.2+
- **Styling**: Tailwind CSS 4.1+ with custom design tokens
- **Routing**: Vue Router 4.6+ with hash-based navigation
- **Icons**: Lucide Vue Next
- **HTTP Client**: Axios
- **Fonts**: Sen (custom), Arial (fallback)

## 📁 Project Structure

```
photo-gear/
├── src/
│   ├── auth/                  # Authentication module
│   │   ├── components/        # Auth-specific components
│   │   ├── layout/            # Auth layout (login/register wrapper)
│   │   ├── pages/             # Login, Register pages
│   │   └── router/            # Auth routes configuration
│   ├── core/                  # Core shared functionality
│   │   ├── components/        # Reusable components
│   │   │   └── base/          # Base UI components (Button, Input, Dropdown, Icon)
│   │   ├── directives/        # Vue directives
│   │   ├── layouts/           # Application layouts
│   │   ├── service/           # API services
│   │   └── utils/             # Utility functions (route collection)
│   ├── module/                # Feature modules (dashboard, dataset, etc.)
│   │   ├── dataset/           # Dataset management module
│   │   │   ├── components/    # Components like file uploaders
│   │   │   ├── pages/         # Dataset related pages
│   │   │   └── router/        # Dataset routes
│   ├── App.vue                # Root component
│   ├── main.ts                # Application entry point
│   ├── router.ts              # Router configuration
│   └── style.css              # Global styles & design tokens
├── public/                    # Static assets
├── index.html                 # HTML entry point
├── vite.config.ts             # Vite configuration
├── tsconfig.json              # TypeScript configuration
└── package.json               # Dependencies and scripts
```

### Color Palette

- **Primary**: `#155DFC` (Blue) - Main brand color
- **Secondary**: `#6A7282` (Gray) - Secondary text and elements
- **Neutral**: Various shades for backgrounds and borders
- **Blue Tints**: For highlights and info states

### Typography

- **Font Family**: Sen (headings), Arial (body)
- **Font Sizes**: 14px (sm), 16px (base), 24px (lg), 28px (xl)

### Spacing System

- Consistent spacing scale: 4px, 8px, 12px, 16px, 24px, 32px

### Components

All base components follow a consistent API pattern:

#### `<base-input>`

```vue
<base-input
  label="Email"
  type="email"
  placeholder="Enter email"
  v-model="email"
  :error="errorMessage"
/>
```

#### `<base-button>`

```vue
<base-button
  variant="primary|secondary|text|ghost"
  size="sm|md|lg"
  type="button|submit|reset"
  :loading="isLoading"
  :disabled="isDisabled"
  block
>
  Button Text
</base-button>
```

#### `<base-drop-down>`

```vue
<base-drop-down
  label="Role"
  :options="roleOptions"
  placeholder="Select role"
  v-model="selectedRole"
  :error="errorMessage"
/>
```

#### `<base-icon>`

```vue
<base-icon name="ChevronDown" :size="16" color="#6A7282" :stroke-width="2" />
```

## 🛠️ Setup & Installation

### Prerequisites

- Node.js 18+
- npm or yarn

### Installation

```bash
# Clone the repository
git clone <repository-url>
cd photo-gear

# Install dependencies
npm install

# Start development server
npm run dev
```

The application will be available at `http://localhost:3000`

## 📜 Available Scripts

```bash
# Development server (port 3000, accessible on network)
npm run dev

# Build for production (with increased memory limit)
npm run build

# Build only (without type checking)
npm run build-only

# Preview production build
npm run preview
```

## 🧩 Module Architecture

### Modular Route System

Routes are automatically collected from module folders using glob patterns:

```typescript
// Modules export their routes
export const authRoutes: RouteRecordRaw[] = [...]

// Routes are auto-collected in router.ts
const routes = await collectRoutes()
```

### Path Aliases

```typescript
@/      → src/
@core/  → src/core/
@auth/  → src/auth/
@module/→ src/module/
```

## 🔐 Authentication

The auth module includes:

- **Login Page**: Email/password authentication
- **Register Page**: Multi-step registration with role selection
- **Auth Layout**: Centered layout with PhotoGear branding

### Auth Routes

- `/auth/login` - Sign in page
- `/auth/register` - Sign up page

## 🎯 Key Features

### Router Configuration

- Hash-based routing (`createWebHashHistory`)
- Async route loading
- Dynamic route registration
- Navigation guards

### State Management

- Reactive state with Vue 3 Composition API
- No external state library (uses Vue's reactivity)

### API Integration

- Axios for HTTP requests
- Centralized service layer in `@core/service`
- Error handling with `await-to-js`

### Type Safety

- Strict TypeScript configuration
- Component prop types
- Type-safe routing
- Comprehensive type definitions

### File Upload

- **`UploadDataSet.vue` Component**: Provides drag-and-drop functionality for ZIP files and a file browser option.
- Uses `defineModel` for two-way data binding of selected files.

## 🏗️ Building Components

### Component Standards

1. Use `<script setup>` syntax
2. Define props with TypeScript interfaces
3. Export types from separate `.type.ts` files
4. Use `defineModel` for v-model binding
5. Follow naming convention: `*.component.vue` for base components

### Example Component Structure

```vue
<template>
  <!-- Component template -->
</template>

<script setup lang="ts">
import type { ComponentProps } from "./component.type";

const props = withDefaults(defineProps<ComponentProps>(), {
  // defaults
});

const modelValue = defineModel<string>();
</script>
```

## 🎨 Styling Guidelines

### Tailwind CSS v4

- Use `@theme` directive in `style.css` for design tokens
- Utility-first approach
- Component-level scoped styles when needed
- Use `tailwind-merge` for dynamic class composition

### CSS Custom Properties

All design tokens are available as CSS variables:

```css
var(--color-primary)
var(--spacing-16)
var(--radius-md)
```

## 📱 Responsive Design

- Mobile-first approach
- Breakpoints: sm, md, lg, xl (Tailwind defaults)
- Flexible layouts with Flexbox/Grid
- Consistent spacing across viewports

## 🔧 Configuration Files

### Vite Config

- Dev server on port 3000
- Production build optimizations
- Preview server on port 5000
- Source maps enabled

### TypeScript Config

- Strict mode enabled
- Path mappings for aliases
- Vue SFC support
- ESNext target

## 🚦 Development Workflow

1. **Feature Development**: Create in `src/module/`
2. **Shared Components**: Add to `src/core/components/base/`
3. **Routing**: Export routes from `module/router/router.ts`
4. **Types**: Define in `*.type.ts` files
5. **Constants**: Define in `*.constant.ts` files

## 📚 Additional Resources

- [Vue 3 Documentation](https://vuejs.org/)
- [TypeScript Guide](https://vuejs.org/guide/typescript/overview.html)
- [Vite Documentation](https://vitejs.dev/)
- [Tailwind CSS v4](https://tailwindcss.com/docs)
- [Vue Router](https://router.vuejs.org/)

## 🤝 Contributing

1. Follow the existing code structure
2. Use TypeScript for all new files
3. Follow component naming conventions
4. Add proper type definitions
5. Update this README for new features

## 📄 License

[Add your license here]

## 👥 Authors

[Add author information here]

---

Built with ❤️ using Vue 3 + TypeScript + Vite
