package app.aptnote.mobile;

import android.os.Bundle;

import androidx.core.view.WindowCompat;
import androidx.core.view.WindowInsetsControllerCompat;

import com.getcapacitor.BridgeActivity;

public class MainActivity extends BridgeActivity {
    @Override
    protected void onCreate(Bundle savedInstanceState) {
        // targetSdk 35 에서는 시스템이 edge-to-edge 를 자동 강제하므로 별도 호출이
        // 필요 없다. EdgeToEdge.enable() 을 호출하면 스플래시 윈도우의 인셋 계산이
        // 깨져 런치 스플래시(중앙 로고)가 화면 상단에 잔류하는 회귀가 발생했다.
        // Play Console 의 edge-to-edge 권장 조치는 (1) targetSdk 35 타겟,
        // (2) deprecated 한 setStatusBarColor/setNavigationBarColor 미사용 으로
        // 이미 충족된다.
        super.onCreate(savedInstanceState);
        applyLightSystemBars();
    }

    private void applyLightSystemBars() {
        // 크림색(#fffaf3) 배경에 맞춰 상태바/내비게이션바 아이콘을 어둡게(라이트) 표시.
        // WindowInsetsControllerCompat 기반이라 deprecated API 가 아니다.
        WindowInsetsControllerCompat controller =
            WindowCompat.getInsetsController(getWindow(), getWindow().getDecorView());
        controller.setAppearanceLightStatusBars(true);
        controller.setAppearanceLightNavigationBars(true);
    }
}
