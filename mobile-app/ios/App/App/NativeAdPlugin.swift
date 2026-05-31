import Foundation
import Capacitor
import UIKit
import GoogleMobileAds

// AdMob 네이티브 고급형 광고를 WebView 카드 그리드 안에 인라인으로 오버레이한다.
//
// 동작은 Android(NativeAdPlugin.kt)와 동일:
//  - JS(NativeAdSlot)가 placeholder 의 문서 좌표(docTop)·크기를 CSS px(=iOS point)로 전달.
//  - 네이티브가 NativeAdView 를 WebView 위에 오버레이로 추가하고, scrollView 의
//    contentOffset 을 KVO 로 추적해 placeholder 위치에 정확히 겹쳐 그린다.
//  - 광고 에셋·클릭·노출은 SDK 의 NativeAdView 가 처리(정책 준수).
//
// ⚠️ Google Mobile Ads SDK 11+ 의 prefix-free Swift API(NativeAd/AdLoader/Request/
//    NativeAdView/MediaView)를 사용한다. 더 낮은 SDK 라면 GAD 접두사로 교체 필요.
@objc(NativeAdPlugin)
public class NativeAdPlugin: CAPPlugin, CAPBridgedPlugin {
    public let identifier = "NativeAdPlugin"
    public let jsName = "NativeAd"
    public let pluginMethods: [CAPPluginMethod] = [
        CAPPluginMethod(name: "isSupported", returnType: CAPPluginReturnPromise),
        CAPPluginMethod(name: "loadSlot", returnType: CAPPluginReturnPromise),
        CAPPluginMethod(name: "updateGeometry", returnType: CAPPluginReturnPromise),
        CAPPluginMethod(name: "hideSlot", returnType: CAPPluginReturnPromise),
        CAPPluginMethod(name: "removeSlot", returnType: CAPPluginReturnPromise),
        CAPPluginMethod(name: "removeAll", returnType: CAPPluginReturnPromise)
    ]

    private final class Slot {
        let container: NativeAdView
        var loader: AdLoader?
        var loaderDelegate: NSObject?     // strong ref 유지용
        var nativeAd: NativeAd?
        var docTop: CGFloat
        var x: CGFloat
        var width: CGFloat
        var height: CGFloat
        // 뷰포트 고정(modal) 슬롯이면 true → reposition 에서 contentOffset 을 빼지 않는다.
        // 이때 docTop 은 문서 절대 Y 가 아니라 뷰포트 기준 Y(rect.top) 이다.
        var fixed: Bool
        init(container: NativeAdView, docTop: CGFloat, x: CGFloat, width: CGFloat, height: CGFloat, fixed: Bool) {
            self.container = container
            self.docTop = docTop; self.x = x; self.width = width; self.height = height; self.fixed = fixed
        }
    }

    private var slots: [String: Slot] = [:]
    private var kvoObserved = false

    private var webView: WKWebView? {
        return (bridge?.viewController as? CAPBridgeViewController)?.webView
    }

    @objc func isSupported(_ call: CAPPluginCall) {
        call.resolve(["supported": true])
    }

    @objc func loadSlot(_ call: CAPPluginCall) {
        guard let slotId = call.getString("slotId"), let adId = call.getString("adId") else {
            call.reject("slotId/adId required"); return
        }
        let npa = call.getBool("npa") ?? false
        let fixed = call.getBool("fixed") ?? false
        let docTop = CGFloat(call.getDouble("docTop") ?? 0)
        let x = CGFloat(call.getDouble("x") ?? 0)
        let width = CGFloat(call.getDouble("width") ?? 0)
        let height = CGFloat(call.getDouble("height") ?? 0)

        DispatchQueue.main.async {
            guard let host = self.webView?.superview else { call.reject("no webview"); return }

            // 기존 슬롯 정리(재로딩).
            if let old = self.slots.removeValue(forKey: slotId) { self.teardown(old) }

            let adView = self.buildAdView()
            adView.isHidden = true
            host.addSubview(adView)

            let slot = Slot(container: adView, docTop: docTop, x: x, width: width, height: height, fixed: fixed)
            self.slots[slotId] = slot
            self.ensureScrollObserver()

            let request = Request()
            if npa {
                let extras = Extras()
                extras.additionalParameters = ["npa": "1"]
                request.register(extras)
            }

            let delegate = NativeAdLoaderProxy(
                onLoad: { [weak self] nativeAd in
                    guard let self = self, let current = self.slots[slotId] else { return }
                    current.nativeAd = nativeAd
                    self.bind(adView: current.container, nativeAd: nativeAd)
                    self.reposition(current)
                    self.notifyListeners("adLoaded", data: ["slotId": slotId])
                },
                onFail: { [weak self] error in
                    self?.notifyListeners("adFailedToLoad", data: ["slotId": slotId, "error": error.localizedDescription])
                }
            )
            slot.loaderDelegate = delegate

            let loader = AdLoader(
                adUnitID: adId,
                rootViewController: self.bridge?.viewController,
                adTypes: [.native],
                options: nil
            )
            loader.delegate = delegate
            slot.loader = loader
            loader.load(request)

            call.resolve(["loaded": true])
        }
    }

    @objc func updateGeometry(_ call: CAPPluginCall) {
        guard let slotId = call.getString("slotId") else { call.reject("slotId required"); return }
        DispatchQueue.main.async {
            guard let slot = self.slots[slotId] else { call.resolve(); return }
            slot.docTop = CGFloat(call.getDouble("docTop") ?? Double(slot.docTop))
            slot.x = CGFloat(call.getDouble("x") ?? Double(slot.x))
            slot.width = CGFloat(call.getDouble("width") ?? Double(slot.width))
            slot.height = CGFloat(call.getDouble("height") ?? Double(slot.height))
            slot.fixed = call.getBool("fixed") ?? slot.fixed
            self.reposition(slot)
            call.resolve()
        }
    }

    @objc func hideSlot(_ call: CAPPluginCall) {
        guard let slotId = call.getString("slotId") else { call.reject("slotId required"); return }
        DispatchQueue.main.async {
            self.slots[slotId]?.container.isHidden = true
            call.resolve()
        }
    }

    @objc func removeSlot(_ call: CAPPluginCall) {
        guard let slotId = call.getString("slotId") else { call.reject("slotId required"); return }
        DispatchQueue.main.async {
            if let slot = self.slots.removeValue(forKey: slotId) { self.teardown(slot) }
            call.resolve()
        }
    }

    @objc func removeAll(_ call: CAPPluginCall) {
        DispatchQueue.main.async {
            self.slots.values.forEach { self.teardown($0) }
            self.slots.removeAll()
            call.resolve()
        }
    }

    // ── 스크롤 추적 ─────────────────────────────────────────────────────────

    private func ensureScrollObserver() {
        guard !kvoObserved, let sv = webView?.scrollView else { return }
        sv.addObserver(self, forKeyPath: "contentOffset", options: [.new], context: nil)
        kvoObserved = true
    }

    public override func observeValue(forKeyPath keyPath: String?, of object: Any?,
                                      change: [NSKeyValueChangeKey: Any]?, context: UnsafeMutableRawPointer?) {
        if keyPath == "contentOffset" {
            DispatchQueue.main.async { self.slots.values.forEach { self.reposition($0) } }
        }
    }

    private func reposition(_ slot: Slot) {
        guard let wv = webView else { return }
        let offsetY = wv.scrollView.contentOffset.y
        // fixed 슬롯은 뷰포트 고정 → contentOffset 을 빼지 않는다(docTop 이 이미 뷰포트 기준).
        let topInWebView = slot.fixed ? slot.docTop : slot.docTop - offsetY
        let originX = wv.frame.minX + slot.x
        let originY = wv.frame.minY + topInWebView

        if slot.nativeAd == nil {
            slot.container.isHidden = true
            return
        }
        let offScreen = (topInWebView + slot.height) < 0 || topInWebView > wv.frame.height
        slot.container.isHidden = offScreen
        if !offScreen {
            slot.container.frame = CGRect(x: originX, y: originY, width: slot.width, height: slot.height)
            slot.container.layoutIfNeeded()
        }
    }

    private func teardown(_ slot: Slot) {
        slot.nativeAd = nil
        slot.loader = nil
        slot.loaderDelegate = nil
        slot.container.removeFromSuperview()
    }

    deinit {
        if kvoObserved, let sv = webView?.scrollView {
            sv.removeObserver(self, forKeyPath: "contentOffset")
        }
    }

    // ── 광고 카드 뷰 구성 (웹 .post-card 와 유사) ──────────────────────────────

    private func buildAdView() -> NativeAdView {
        let adView = NativeAdView()
        adView.backgroundColor = .white
        adView.layer.cornerRadius = 12
        adView.layer.borderWidth = 1
        adView.layer.borderColor = UIColor(red: 0.91, green: 0.90, blue: 0.86, alpha: 1).cgColor // #E8E6DC
        adView.clipsToBounds = true

        let media = MediaView()
        media.translatesAutoresizingMaskIntoConstraints = false
        media.backgroundColor = UIColor(red: 0.925, green: 0.918, blue: 0.890, alpha: 1) // #ECEAE3
        adView.addSubview(media)
        adView.mediaView = media

        let badge = UILabel()
        badge.text = " 광고 "
        badge.font = .systemFont(ofSize: 9, weight: .bold)
        badge.textColor = UIColor(red: 0.46, green: 0.45, blue: 0.44, alpha: 1) // #767370
        badge.backgroundColor = UIColor.white.withAlphaComponent(0.92)
        badge.layer.cornerRadius = 4
        badge.layer.borderWidth = 1
        badge.layer.borderColor = UIColor(red: 0.91, green: 0.90, blue: 0.86, alpha: 1).cgColor
        badge.clipsToBounds = true
        badge.translatesAutoresizingMaskIntoConstraints = false
        adView.addSubview(badge)

        let headline = UILabel()
        headline.font = .systemFont(ofSize: 17, weight: .bold)
        headline.textColor = UIColor(red: 0.173, green: 0.161, blue: 0.145, alpha: 1) // #2C2925
        headline.numberOfLines = 2
        headline.translatesAutoresizingMaskIntoConstraints = false
        adView.addSubview(headline)
        adView.headlineView = headline

        let body = UILabel()
        body.font = .systemFont(ofSize: 12, weight: .regular)
        body.textColor = UIColor(red: 0.46, green: 0.45, blue: 0.44, alpha: 1)
        body.numberOfLines = 2
        body.translatesAutoresizingMaskIntoConstraints = false
        adView.addSubview(body)
        adView.bodyView = body

        let cta = UILabel()
        cta.font = .systemFont(ofSize: 13, weight: .bold)
        cta.textColor = .white
        cta.textAlignment = .center
        cta.backgroundColor = UIColor(red: 0.435, green: 0.455, blue: 0.435, alpha: 1) // #6F746F
        cta.isUserInteractionEnabled = true
        cta.translatesAutoresizingMaskIntoConstraints = false
        adView.addSubview(cta)
        adView.callToActionView = cta

        NSLayoutConstraint.activate([
            media.topAnchor.constraint(equalTo: adView.topAnchor),
            media.leadingAnchor.constraint(equalTo: adView.leadingAnchor),
            media.trailingAnchor.constraint(equalTo: adView.trailingAnchor),
            media.heightAnchor.constraint(equalTo: adView.heightAnchor, multiplier: 0.42),

            badge.topAnchor.constraint(equalTo: adView.topAnchor, constant: 9),
            badge.trailingAnchor.constraint(equalTo: adView.trailingAnchor, constant: -9),

            headline.topAnchor.constraint(equalTo: media.bottomAnchor, constant: 13),
            headline.leadingAnchor.constraint(equalTo: adView.leadingAnchor, constant: 16),
            headline.trailingAnchor.constraint(equalTo: adView.trailingAnchor, constant: -16),

            body.topAnchor.constraint(equalTo: headline.bottomAnchor, constant: 6),
            body.leadingAnchor.constraint(equalTo: adView.leadingAnchor, constant: 16),
            body.trailingAnchor.constraint(equalTo: adView.trailingAnchor, constant: -16),

            cta.leadingAnchor.constraint(equalTo: adView.leadingAnchor),
            cta.trailingAnchor.constraint(equalTo: adView.trailingAnchor),
            cta.bottomAnchor.constraint(equalTo: adView.bottomAnchor),
            cta.heightAnchor.constraint(equalToConstant: 42)
        ])
        return adView
    }

    private func bind(adView: NativeAdView, nativeAd: NativeAd) {
        (adView.headlineView as? UILabel)?.text = nativeAd.headline
        (adView.bodyView as? UILabel)?.text = nativeAd.body
        adView.bodyView?.isHidden = (nativeAd.body == nil)
        (adView.callToActionView as? UILabel)?.text = nativeAd.callToAction
        adView.callToActionView?.isHidden = (nativeAd.callToAction == nil)
        adView.mediaView?.mediaContent = nativeAd.mediaContent
        // 필수: 에셋 등록 확정.
        adView.nativeAd = nativeAd
    }
}

// AdLoader delegate 프록시 — 슬롯별 클로저로 콜백 전달.
private final class NativeAdLoaderProxy: NSObject, NativeAdLoaderDelegate {
    let onLoad: (NativeAd) -> Void
    let onFail: (Error) -> Void
    init(onLoad: @escaping (NativeAd) -> Void, onFail: @escaping (Error) -> Void) {
        self.onLoad = onLoad; self.onFail = onFail
    }
    func adLoader(_ adLoader: AdLoader, didReceive nativeAd: NativeAd) { onLoad(nativeAd) }
    func adLoader(_ adLoader: AdLoader, didFailToReceiveAdWithError error: Error) { onFail(error) }
}
