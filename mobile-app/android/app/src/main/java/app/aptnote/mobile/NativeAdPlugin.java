package app.aptnote.mobile;

import android.graphics.Color;
import android.graphics.drawable.GradientDrawable;
import android.util.TypedValue;
import android.view.Gravity;
import android.view.ViewGroup;
import android.widget.Button;
import android.widget.FrameLayout;
import android.widget.LinearLayout;
import android.widget.TextView;

import com.getcapacitor.Plugin;
import com.getcapacitor.PluginCall;
import com.getcapacitor.PluginMethod;
import com.getcapacitor.annotation.CapacitorPlugin;

import com.google.android.gms.ads.AdListener;
import com.google.android.gms.ads.AdLoader;
import com.google.android.gms.ads.AdRequest;
import com.google.android.gms.ads.LoadAdError;
import com.google.android.gms.ads.MobileAds;
import com.google.android.gms.ads.nativead.MediaView;
import com.google.android.gms.ads.nativead.NativeAd;
import com.google.android.gms.ads.nativead.NativeAdView;

/**
 * AdMob Native Advanced 광고를, JS 가 측정해 넘긴 화면 좌표/크기에 맞춰
 * 공식 NativeAdView 로 직접 렌더한다. (서드파티 플러그인/HTML 자산 추출 없이
 * SDK 표준 경로로 렌더 → 노출/클릭 추적 정상 = 정책 준수.)
 *
 * 좌표계: JS getBoundingClientRect(CSS px) * devicePixelRatio = 물리 px.
 * Capacitor WebView 는 android.R.id.content 를 가득 채우므로, content 의 (0,0)
 * 과 WebView 뷰포트 (0,0) 이 일치 → 그 좌표에 그대로 overlay 한다.
 */
@CapacitorPlugin(name = "NativeAd")
public class NativeAdPlugin extends Plugin {

    // Google 공개 테스트 — Native Advanced (Android)
    private static final String TEST_NATIVE_ANDROID = "ca-app-pub-3940256099942544/2247696110";

    private NativeAdView adView;
    private NativeAd nativeAd;
    // show() 호출 후 hide() 전까지만 렌더. 비동기 로드가 끝나기 전에 다이얼로그가
    // 닫히면(=hide) 뒤늦게 도착한 광고가 화면에 떠 있는 orphan 을 방지.
    private boolean active;

    @Override
    public void load() {
        // 이미 초기화돼 있으면 idempotent. 종료 다이얼로그 진입 전 미초기화 대비.
        try {
            MobileAds.initialize(getContext(), initializationStatus -> { });
        } catch (Throwable ignored) { }
    }

    @PluginMethod
    public void show(final PluginCall call) {
        final boolean testing = Boolean.TRUE.equals(call.getBoolean("testing", true));
        final String configuredId = call.getString("adUnitId", TEST_NATIVE_ANDROID);
        final String adUnitId = (testing || configuredId == null) ? TEST_NATIVE_ANDROID : configuredId;
        final int x = call.getInt("x", 0);
        final int y = call.getInt("y", 0);
        final int width = call.getInt("width", 0);
        final int height = call.getInt("height", 0);

        active = true;
        getActivity().runOnUiThread(() -> {
            try {
                AdLoader adLoader = new AdLoader.Builder(getContext(), adUnitId)
                    .forNativeAd(ad -> {
                        if (!active) {
                            // 이미 다이얼로그가 닫힘 → 렌더하지 않고 폐기.
                            ad.destroy();
                            return;
                        }
                        if (nativeAd != null) {
                            nativeAd.destroy();
                        }
                        nativeAd = ad;
                        renderAd(ad, x, y, width, height);
                    })
                    .withAdListener(new AdListener() {
                        @Override
                        public void onAdFailedToLoad(LoadAdError error) {
                            call.reject("load_failed: " + error.getCode() + " " + error.getMessage());
                        }
                        @Override
                        public void onAdLoaded() {
                            call.resolve();
                        }
                    })
                    .build();
                adLoader.loadAd(new AdRequest.Builder().build());
            } catch (Throwable t) {
                call.reject("native_ad_error: " + t.getMessage());
            }
        });
    }

    @PluginMethod
    public void hide(final PluginCall call) {
        active = false;
        getActivity().runOnUiThread(() -> {
            removeAdView();
            call.resolve();
        });
    }

    private void renderAd(NativeAd ad, int x, int y, int width, int height) {
        removeAdView();

        NativeAdView nav = new NativeAdView(getContext());

        LinearLayout root = new LinearLayout(getContext());
        root.setOrientation(LinearLayout.VERTICAL);
        GradientDrawable bg = new GradientDrawable();
        bg.setColor(Color.WHITE);
        bg.setCornerRadius(dp(12));
        root.setBackground(bg);
        int pad = dp(12);
        root.setPadding(pad, pad, pad, pad);
        root.setLayoutParams(new FrameLayout.LayoutParams(
            FrameLayout.LayoutParams.MATCH_PARENT, FrameLayout.LayoutParams.MATCH_PARENT));

        // "광고" 표기 (네이티브 광고 정책상 광고 식별 표기 필요)
        TextView badge = new TextView(getContext());
        badge.setText("광고");
        badge.setTextColor(Color.WHITE);
        badge.setTextSize(TypedValue.COMPLEX_UNIT_SP, 10);
        GradientDrawable badgeBg = new GradientDrawable();
        badgeBg.setColor(Color.parseColor("#9CA3AF"));
        badgeBg.setCornerRadius(dp(4));
        badge.setBackground(badgeBg);
        badge.setPadding(dp(6), dp(2), dp(6), dp(2));
        LinearLayout.LayoutParams badgeLp = new LinearLayout.LayoutParams(
            LinearLayout.LayoutParams.WRAP_CONTENT, LinearLayout.LayoutParams.WRAP_CONTENT);
        badge.setLayoutParams(badgeLp);
        root.addView(badge);

        // 헤드라인 (필수)
        TextView headline = new TextView(getContext());
        headline.setText(ad.getHeadline());
        headline.setTextColor(Color.parseColor("#2C2925"));
        headline.setTextSize(TypedValue.COMPLEX_UNIT_SP, 16);
        headline.setMaxLines(2);
        headline.setPadding(0, dp(6), 0, 0);
        root.addView(headline);
        nav.setHeadlineView(headline);

        // 본문 (선택)
        if (ad.getBody() != null) {
            TextView body = new TextView(getContext());
            body.setText(ad.getBody());
            body.setTextColor(Color.parseColor("#6B6660"));
            body.setTextSize(TypedValue.COMPLEX_UNIT_SP, 13);
            body.setMaxLines(2);
            body.setPadding(0, dp(4), 0, 0);
            root.addView(body);
            nav.setBodyView(body);
        }

        // 미디어 (선택) — 남는 공간을 채움
        MediaView mediaView = new MediaView(getContext());
        LinearLayout.LayoutParams mediaLp = new LinearLayout.LayoutParams(
            LinearLayout.LayoutParams.MATCH_PARENT, 0, 1f);
        mediaLp.topMargin = dp(8);
        mediaView.setLayoutParams(mediaLp);
        root.addView(mediaView);
        nav.setMediaView(mediaView);

        // CTA 버튼 (선택)
        if (ad.getCallToAction() != null) {
            Button cta = new Button(getContext());
            cta.setText(ad.getCallToAction());
            cta.setAllCaps(false);
            cta.setTextColor(Color.WHITE);
            GradientDrawable ctaBg = new GradientDrawable();
            ctaBg.setColor(Color.parseColor("#D97757"));
            ctaBg.setCornerRadius(dp(10));
            cta.setBackground(ctaBg);
            LinearLayout.LayoutParams ctaLp = new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT, dp(44));
            ctaLp.topMargin = dp(8);
            cta.setLayoutParams(ctaLp);
            root.addView(cta);
            nav.setCallToActionView(cta);
        }

        nav.addView(root);
        nav.setNativeAd(ad);

        FrameLayout.LayoutParams lp = new FrameLayout.LayoutParams(
            width > 0 ? width : FrameLayout.LayoutParams.WRAP_CONTENT,
            height > 0 ? height : FrameLayout.LayoutParams.WRAP_CONTENT);
        lp.gravity = Gravity.TOP | Gravity.START;
        lp.leftMargin = x;
        lp.topMargin = y;

        ViewGroup content = (ViewGroup) getActivity().findViewById(android.R.id.content);
        content.addView(nav, lp);
        adView = nav;
    }

    private void removeAdView() {
        if (adView != null) {
            ViewGroup parent = (ViewGroup) adView.getParent();
            if (parent != null) {
                parent.removeView(adView);
            }
            adView.destroy();
            adView = null;
        }
        if (nativeAd != null) {
            nativeAd.destroy();
            nativeAd = null;
        }
    }

    @Override
    protected void handleOnDestroy() {
        removeAdView();
        super.handleOnDestroy();
    }

    private int dp(int value) {
        return (int) TypedValue.applyDimension(
            TypedValue.COMPLEX_UNIT_DIP, value, getContext().getResources().getDisplayMetrics());
    }
}
