package app.aptnote.mobile;

import android.os.Bundle;

import androidx.activity.EdgeToEdge;
import androidx.core.view.WindowCompat;
import androidx.core.view.WindowInsetsControllerCompat;

import com.getcapacitor.BridgeActivity;

public class MainActivity extends BridgeActivity {
    @Override
    protected void onCreate(Bundle savedInstanceState) {
        // Android 15(SDK 35)부터 edge-to-edge가 기본 적용되며,
        // Window.setStatusBarColor()/setNavigationBarColor()는 지원이 중단됐다.
        // 표준 edge-to-edge API로 시스템 바를 투명 처리하고, 웹 레이어가
        // env(safe-area-inset-*)로 인셋을 처리하도록 한다 (viewport-fit=cover).
        EdgeToEdge.enable(this);
        super.onCreate(savedInstanceState);
        applyLightSystemBars();
    }

    private void applyLightSystemBars() {
        // 크림색(#fffaf3) 배경에 맞춰 상태바/내비게이션바 아이콘을 어둡게(라이트) 표시.
        WindowInsetsControllerCompat controller =
            WindowCompat.getInsetsController(getWindow(), getWindow().getDecorView());
        controller.setAppearanceLightStatusBars(true);
        controller.setAppearanceLightNavigationBars(true);
    }
}
