import { Capacitor, registerPlugin } from "@capacitor/core";

type AptNoteAdsPlugin = {
  showBanners(options: { topAdId?: string; bottomAdId?: string }): Promise<void>;
  hideBanners(): Promise<void>;
};

const AptNoteAds = registerPlugin<AptNoteAdsPlugin>("AptNoteAds");

export const ADMOB_AD_UNITS = {
  frontTopBanner: "ca-app-pub-8234120897033274/1147605916",
  frontBottomBanner: "ca-app-pub-8234120897033274/9844353587",
  frontNativeGrid: "ca-app-pub-8234120897033274/7218190241",
  postTopBanner: "ca-app-pub-8234120897033274/6881261825"
};

export async function showAdBanners(topAdId?: string, bottomAdId?: string): Promise<void> {
  if (!Capacitor.isNativePlatform()) return;
  await AptNoteAds.showBanners({ topAdId, bottomAdId });
}

export async function hideAdBanners(): Promise<void> {
  if (!Capacitor.isNativePlatform()) return;
  await AptNoteAds.hideBanners();
}
