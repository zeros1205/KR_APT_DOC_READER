import type { CapacitorConfig } from "@capacitor/cli";

const config: CapacitorConfig = {
  appId: "app.aptnote.mobile",
  appName: "청약노트",
  webDir: "dist",
  bundledWebRuntime: false,
  ios: {
    contentInset: "never",
    scrollEnabled: true,
    backgroundColor: "#fffaf3",
    preferredContentMode: "mobile"
  },
  plugins: {
    SplashScreen: {
      launchAutoHide: true,
      backgroundColor: "#fffaf3",
      showSpinner: false,
      iosSpinnerStyle: "small",
      spinnerColor: "#d97757",
      launchFadeOutDuration: 300
    },
    PushNotifications: {
      presentationOptions: ["badge", "sound", "alert"]
    },
    Keyboard: {
      resize: "body",
      resizeOnFullScreen: true
    }
  }
};

export default config;
