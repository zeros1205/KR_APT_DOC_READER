import UIKit
import Capacitor
import WebKit

class MainViewController: CAPBridgeViewController {
    override func viewDidLoad() {
        super.viewDidLoad()
        if let webView = self.webView {
            webView.allowsBackForwardNavigationGestures = true
        }
    }
}
