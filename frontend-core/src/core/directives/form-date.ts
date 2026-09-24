import type { DirectiveBinding } from "vue";

const formatDate = (el: HTMLElement, binding: DirectiveBinding) => {
  const val = binding.value;

  if (val === null || val === undefined || val === "") {
    el.innerText = "";
    return;
  }

  let date: Date;

  if (typeof val === "string") {
    date = new Date(val);

    // If parsing fails, try to normalize fractional seconds (truncate to milliseconds)
    if (isNaN(date.getTime())) {
      // Trim fractional seconds to 3 digits: .123456 -> .123
      const normalized = val.replace(/(\.\d{3})\d+/, "$1");
      date = new Date(normalized);
    }

    // If still invalid, remove fractional seconds entirely and retry
    if (isNaN(date.getTime())) {
      const noFrac = val.replace(/\.\d+/, "");
      date = new Date(noFrac);
    }
  } else {
    date = new Date(val as any);
  }

  if (isNaN(date.getTime())) {
    el.innerText = "Invalid Date";
    return;
  }

  // Determine format: default = date only, 'datetime' = date + time
  const arg = binding.arg;
  const mods = binding.modifiers || {};
  const wantDateTime =
    arg === "datetime" || arg === "withTime" || mods.datetime || mods.time || mods.withTime;

  const pad = (n: number) => String(n).padStart(2, "0");
  const y = date.getFullYear();
  const m = pad(date.getMonth() + 1);
  const d = pad(date.getDate());
  const hh = pad(date.getHours());
  const mm = pad(date.getMinutes());

  if (wantDateTime) {
    // format as ISO-like: YYYY-MM-DD HH:MM
    el.innerText = `${y}-${m}-${d} ${hh}:${mm}`;
  } else {
    // date only: YYYY-MM-DD
    el.innerText = `${y}-${m}-${d}`;
  }
};

export default {
  mounted(el: HTMLElement, binding: DirectiveBinding) {
    formatDate(el, binding);
  },
  updated(el: HTMLElement, binding: DirectiveBinding) {
    formatDate(el, binding);
  },
};
