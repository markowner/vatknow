import { defineStore } from "pinia";
import { ref } from "vue";
import { SpacesApi, type Space } from "@/api";

export const useSpacesStore = defineStore("spaces", () => {
  const items = ref<Space[]>([]);

  async function refresh() {
    items.value = await SpacesApi.list();
  }

  return { items, refresh };
});
