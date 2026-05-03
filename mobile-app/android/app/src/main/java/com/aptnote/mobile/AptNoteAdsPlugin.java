package com.aptnote.mobile;

import android.app.Activity;
import android.view.Gravity;
import android.view.ViewGroup;
import android.widget.FrameLayout;
import com.getcapacitor.Plugin;
import com.getcapacitor.PluginCall;
import com.getcapacitor.PluginMethod;
import com.getcapacitor.annotation.CapacitorPlugin;
import com.google.android.gms.ads.AdRequest;
import com.google.android.gms.ads.AdSize;
import com.google.android.gms.ads.AdView;
import com.google.android.gms.ads.MobileAds;

@CapacitorPlugin(name = "AptNoteAds")
public class AptNoteAdsPlugin extends Plugin {
    private AdView topBanner;
    private AdView bottomBanner;
    private boolean initialized;

    @PluginMethod
    public void showBanners(PluginCall call) {
        String topAdId = call.getString("topAdId", "");
        String bottomAdId = call.getString("bottomAdId", "");

        getActivity().runOnUiThread(() -> {
            ensureInitialized();
            topBanner = showOrRemove(topBanner, topAdId, Gravity.TOP);
            bottomBanner = showOrRemove(bottomBanner, bottomAdId, Gravity.BOTTOM);
            call.resolve();
        });
    }

    @PluginMethod
    public void hideBanners(PluginCall call) {
        getActivity().runOnUiThread(() -> {
            topBanner = remove(topBanner);
            bottomBanner = remove(bottomBanner);
            call.resolve();
        });
    }

    private void ensureInitialized() {
        if (initialized) return;
        MobileAds.initialize(getActivity());
        initialized = true;
    }

    private AdView showOrRemove(AdView current, String adUnitId, int gravity) {
        if (adUnitId == null || adUnitId.trim().isEmpty()) {
            return remove(current);
        }
        if (current != null && adUnitId.equals(current.getAdUnitId())) {
            current.setVisibility(AdView.VISIBLE);
            return current;
        }
        current = remove(current);
        Activity activity = getActivity();
        AdView next = new AdView(activity);
        next.setAdSize(AdSize.BANNER);
        next.setAdUnitId(adUnitId);

        FrameLayout.LayoutParams params = new FrameLayout.LayoutParams(
            ViewGroup.LayoutParams.MATCH_PARENT,
            ViewGroup.LayoutParams.WRAP_CONTENT
        );
        params.gravity = gravity | Gravity.CENTER_HORIZONTAL;
        activity.addContentView(next, params);
        next.loadAd(new AdRequest.Builder().build());
        return next;
    }

    private AdView remove(AdView adView) {
        if (adView == null) return null;
        ViewGroup parent = (ViewGroup) adView.getParent();
        if (parent != null) {
            parent.removeView(adView);
        }
        adView.destroy();
        return null;
    }
}
