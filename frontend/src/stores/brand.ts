import { defineStore } from "pinia";
import { computed, ref } from "vue";
import { SiteApi, type SiteBrand } from "@/api";

/**
 * 站点品牌信息（标题、副标题、Logo）。
 *
 * 侧边栏、登录页、浏览器标题都要用，所以放 store 里只拉一次；
 * 设置页改完后调 set() 立即同步到全站，不用刷新页面。
 */
export const useBrandStore = defineStore("brand", () => {
  const brand = ref<SiteBrand>({
    site_name: "VatKnow",
    site_tagline: "Docs · API",
    has_logo: false,
    logo_version: 0,
    is_site_admin: false,
  });
  const loaded = ref(false);

  const siteName = computed(() => brand.value.site_name || "VatKnow");
  const tagline = computed(() => brand.value.site_tagline || "");
  const isSiteAdmin = computed(() => brand.value.is_site_admin);
  /** 没上传过就返回 null，交给 SiteLogo 回落到内置图形。 */
  const logoUrl = computed(() =>
    brand.value.has_logo ? SiteApi.logoUrl(brand.value.logo_version) : null,
  );

  function set(next: SiteBrand) {
    brand.value = next;
    loaded.value = true;
    document.title = next.site_name ? `${next.site_name} 知识库` : "知识库";
  }

  /** 未登录时读公开接口；已登录时读带权限的那个。 */
  async function load(authed: boolean) {
    try {
      set(authed ? await SiteApi.brandMine() : await SiteApi.brand());
    } catch {
      // 品牌信息拿不到不该挡住页面，用默认值继续。
      loaded.value = true;
    }
  }

  return { brand, loaded, siteName, tagline, isSiteAdmin, logoUrl, set, load };
});
