package app.aptnote.mobile

import android.os.Bundle
import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import android.widget.FrameLayout
import com.getcapacitor.JSObject
import com.getcapacitor.Plugin
import com.getcapacitor.PluginCall
import com.getcapacitor.PluginMethod
import com.getcapacitor.annotation.CapacitorPlugin
import com.google.ads.mediation.admob.AdMobAdapter
import com.google.android.gms.ads.AdListener
import com.google.android.gms.ads.AdLoader
import com.google.android.gms.ads.AdRequest
import com.google.android.gms.ads.LoadAdError
import com.google.android.gms.ads.nativead.MediaView
import com.google.android.gms.ads.nativead.NativeAd
import com.google.android.gms.ads.nativead.NativeAdView

/**
 * AdMob 네이티브 고급형 광고를 WebView 카드 그리드 안에 인라인으로 오버레이한다.
 *
 * @capacitor-community/admob 가 네이티브 광고를 지원하지 않으므로 전용으로 구현.
 *
 * 동작:
 *  - JS(NativeAdSlot) 가 placeholder 의 문서 좌표(docTop)·크기를 CSS px 로 넘긴다.
 *  - 네이티브는 NativeAdView 를 WebView 의 부모 뷰그룹에 오버레이로 추가하고,
 *    WebView 스크롤(scrollY)을 직접 추적해 placeholder 위치에 정확히 겹쳐 그린다.
 *  - 광고 에셋·클릭·노출은 모두 SDK 의 NativeAdView 가 처리(정책 준수).
 */
@CapacitorPlugin(name = "NativeAd")
class NativeAdPlugin : Plugin() {

    private class Slot(
        val adView: NativeAdView,
        var nativeAd: NativeAd?,
        var docTopCss: Float,
        var xCss: Float,
        var widthCss: Float,
        var heightCss: Float,
        // 뷰포트 고정(modal) 슬롯이면 true → reposition 에서 scrollY 를 빼지 않는다.
        // 이때 docTopCss 는 문서 절대 Y 가 아니라 뷰포트 기준 Y(rect.top) 이다.
        var fixed: Boolean
    )

    private val slots = HashMap<String, Slot>()
    private var scrollListenerAttached = false

    private val density: Float
        get() = bridge.activity.resources.displayMetrics.density

    private fun webView() = bridge.webView

    /** WebView 의 부모(같은 좌표계). 여기에 광고 오버레이를 add 한다. */
    private fun overlayParent(): ViewGroup? = webView().parent as? ViewGroup

    @PluginMethod
    fun isSupported(call: PluginCall) {
        val ret = JSObject()
        ret.put("supported", true)
        call.resolve(ret)
    }

    @PluginMethod
    fun loadSlot(call: PluginCall) {
        val slotId = call.getString("slotId") ?: run { call.reject("slotId required"); return }
        val adId = call.getString("adId") ?: run { call.reject("adId required"); return }
        val npa = call.getBoolean("npa", false) ?: false
        val fixed = call.getBoolean("fixed", false) ?: false
        val docTop = call.getFloat("docTop") ?: 0f
        val x = call.getFloat("x") ?: 0f
        val width = call.getFloat("width") ?: 0f
        val height = call.getFloat("height") ?: 0f

        bridge.activity.runOnUiThread {
            // 이미 있으면 먼저 정리(재로딩).
            slots.remove(slotId)?.let { teardown(it) }

            val inflater = LayoutInflater.from(bridge.activity)
            val adView = inflater.inflate(R.layout.native_ad_card, null, false) as NativeAdView
            adView.visibility = View.GONE

            val slot = Slot(adView, null, docTop, x, width, height, fixed)
            slots[slotId] = slot

            val parent = overlayParent()
            if (parent != null) {
                val lp = FrameLayout.LayoutParams(
                    (width * density).toInt(),
                    (height * density).toInt()
                )
                parent.addView(adView, lp)
            }
            ensureScrollListener()

            val adRequest = AdRequest.Builder().apply {
                if (npa) {
                    val extras = Bundle().apply { putString("npa", "1") }
                    addNetworkExtrasBundle(AdMobAdapter::class.java, extras)
                }
            }.build()

            val adLoader = AdLoader.Builder(bridge.activity, adId)
                .forNativeAd { nativeAd ->
                    val current = slots[slotId]
                    if (current == null) {
                        nativeAd.destroy()
                        return@forNativeAd
                    }
                    current.nativeAd?.destroy()
                    current.nativeAd = nativeAd
                    bindNativeAd(current.adView, nativeAd)
                    reposition(slotId, current)
                    emit("adLoaded", slotId, null)
                }
                .withAdListener(object : AdListener() {
                    override fun onAdFailedToLoad(error: LoadAdError) {
                        emit("adFailedToLoad", slotId, error.message)
                    }

                    override fun onAdClicked() {
                        emit("adClicked", slotId, null)
                    }

                    override fun onAdImpression() {
                        emit("adImpression", slotId, null)
                    }
                })
                .build()

            adLoader.loadAd(adRequest)

            val ret = JSObject()
            ret.put("loaded", true)
            call.resolve(ret)
        }
    }

    @PluginMethod
    fun updateGeometry(call: PluginCall) {
        val slotId = call.getString("slotId") ?: run { call.reject("slotId required"); return }
        bridge.activity.runOnUiThread {
            val slot = slots[slotId] ?: run { call.resolve(); return@runOnUiThread }
            slot.docTopCss = call.getFloat("docTop") ?: slot.docTopCss
            slot.xCss = call.getFloat("x") ?: slot.xCss
            slot.widthCss = call.getFloat("width") ?: slot.widthCss
            slot.heightCss = call.getFloat("height") ?: slot.heightCss
            slot.fixed = call.getBoolean("fixed", slot.fixed) ?: slot.fixed
            // 크기 변경 반영.
            (slot.adView.layoutParams as? FrameLayout.LayoutParams)?.let { lp ->
                lp.width = (slot.widthCss * density).toInt()
                lp.height = (slot.heightCss * density).toInt()
                slot.adView.layoutParams = lp
            }
            reposition(slotId, slot)
            call.resolve()
        }
    }

    @PluginMethod
    fun hideSlot(call: PluginCall) {
        val slotId = call.getString("slotId") ?: run { call.reject("slotId required"); return }
        bridge.activity.runOnUiThread {
            slots[slotId]?.adView?.visibility = View.GONE
            call.resolve()
        }
    }

    @PluginMethod
    fun removeSlot(call: PluginCall) {
        val slotId = call.getString("slotId") ?: run { call.reject("slotId required"); return }
        bridge.activity.runOnUiThread {
            slots.remove(slotId)?.let { teardown(it) }
            call.resolve()
        }
    }

    @PluginMethod
    fun removeAll(call: PluginCall) {
        bridge.activity.runOnUiThread {
            slots.values.forEach { teardown(it) }
            slots.clear()
            call.resolve()
        }
    }

    // ── 내부 ──────────────────────────────────────────────────────────────

    private fun teardown(slot: Slot) {
        slot.nativeAd?.destroy()
        slot.nativeAd = null
        (slot.adView.parent as? ViewGroup)?.removeView(slot.adView)
    }

    private fun ensureScrollListener() {
        if (scrollListenerAttached) return
        webView().setOnScrollChangeListener { _, _, _, _, _ ->
            repositionAll()
        }
        scrollListenerAttached = true
    }

    private fun repositionAll() {
        for ((id, slot) in slots) reposition(id, slot)
    }

    private fun reposition(slotId: String, slot: Slot) {
        val wv = webView()
        // fixed 슬롯은 뷰포트 고정 → 스크롤을 빼지 않는다(docTopCss 가 이미 뷰포트 기준).
        val topPx = if (slot.fixed) slot.docTopCss * density else slot.docTopCss * density - wv.scrollY
        val leftPx = slot.xCss * density
        val heightPx = slot.heightCss * density

        // 광고가 아직 바인딩되지 않았으면 숨김 유지.
        if (slot.nativeAd == null) {
            slot.adView.visibility = View.GONE
            return
        }
        // WebView 가시 영역 밖이면 숨김(불필요한 노출 방지).
        val offScreen = topPx + heightPx < 0f || topPx > wv.height.toFloat()
        if (offScreen) {
            slot.adView.visibility = View.GONE
            return
        }
        slot.adView.visibility = View.VISIBLE
        slot.adView.x = wv.x + leftPx
        slot.adView.y = wv.y + topPx
    }

    private fun bindNativeAd(adView: NativeAdView, nativeAd: NativeAd) {
        val media = adView.findViewById<MediaView>(R.id.ad_media)
        val headline = adView.findViewById<android.widget.TextView>(R.id.ad_headline)
        val body = adView.findViewById<android.widget.TextView>(R.id.ad_body)
        val cta = adView.findViewById<android.widget.TextView>(R.id.ad_cta)
        val advertiser = adView.findViewById<android.widget.TextView>(R.id.ad_advertiser)

        adView.mediaView = media
        adView.headlineView = headline
        adView.bodyView = body
        adView.callToActionView = cta
        adView.advertiserView = advertiser

        headline.text = nativeAd.headline
        nativeAd.mediaContent?.let { media.mediaContent = it }
        if (nativeAd.body != null) {
            body.visibility = View.VISIBLE
            body.text = nativeAd.body
        } else {
            body.visibility = View.GONE
        }
        if (nativeAd.callToAction != null) {
            cta.visibility = View.VISIBLE
            cta.text = nativeAd.callToAction
        } else {
            cta.visibility = View.GONE
        }
        if (nativeAd.advertiser != null) {
            advertiser.visibility = View.VISIBLE
            advertiser.text = nativeAd.advertiser
        } else {
            advertiser.visibility = View.GONE
        }

        // 필수: 에셋 바인딩을 SDK 에 확정.
        adView.setNativeAd(nativeAd)
    }

    override fun handleOnDestroy() {
        super.handleOnDestroy()
        bridge.activity.runOnUiThread {
            slots.values.forEach { teardown(it) }
            slots.clear()
        }
    }

    private fun emit(event: String, slotId: String, error: String?) {
        val data = JSObject()
        data.put("slotId", slotId)
        if (error != null) data.put("error", error)
        notifyListeners(event, data)
    }
}
