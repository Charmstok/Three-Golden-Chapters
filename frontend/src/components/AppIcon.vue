<script setup lang="ts">
defineProps<{ name: string; size?: number }>();
const paths: Record<string, string> = {
  menu: "M4 6h16 M4 12h16 M4 18h16",
  plus: "M12 5v14 M5 12h14",
  back: "M19 12H5 M10 7l-5 5 5 5",
  settings:
    "M12 8a4 4 0 1 0 0 8 4 4 0 0 0 0-8 M5 3l3 2 4-2 4 2 3-2 2 4-2 3 2 4-2 3-3-1-4 2-4-2-3 1-2-3 2-4-2-3z",
  book: "M4 4h6a2 2 0 0 1 2 2v15a4 4 0 0 0-4-3H4z M20 4h-6a2 2 0 0 0-2 2v15a4 4 0 0 1 4-3h4z",
  upload: "M12 16V3 M7 8l5-5 5 5 M4 15v5a1 1 0 0 0 1 1h14a1 1 0 0 0 1-1v-5",
  arrow: "M5 12h14 M14 7l5 5-5 5",
  spark: "m12 3 2.8 6.2L21 12l-6.2 2.8L12 21l-2.8-6.2L3 12l6.2-2.8z",
  download: "M12 3v13 M7 11l5 5 5-5 M4 17v3h16v-3",
  search: "M21 21l-5-5 M18 10a8 8 0 1 1-16 0 8 8 0 0 1 16 0",
  close: "m6 6 12 12 M6 18 18 6",
  check: "m5 12 4 4L19 6",
  trash: "M3 6h18 M9 6V3h6v3 M5 6l1 15h12l1-15 M10 10v7 M14 10v7",
  refresh: "M20 7v5h-5 M4 17v-5h5 M19 7a8 8 0 0 0-14-1 M5 17a8 8 0 0 0 14 1",
  grid: "M3 3h7v7H3z M14 3h7v7h-7z M3 14h7v7H3z M14 14h7v7h-7z",
  clock: "M12 7v5l3 2 M22 12a10 10 0 1 1-20 0 10 10 0 0 1 20 0",
};
</script>

<template>
  <svg
    :width="size || 20"
    :height="size || 20"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    stroke-width="1.65"
    stroke-linecap="round"
    stroke-linejoin="round"
    aria-hidden="true"
  >
    <path :d="paths[name] || paths.book" />
  </svg>
</template>
