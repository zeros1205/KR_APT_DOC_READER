package com.aptnote.mobile;

import android.os.Bundle;
import com.getcapacitor.BridgeActivity;

public class MainActivity extends BridgeActivity {
    @Override
    protected void onCreate(Bundle savedInstanceState) {
        registerPlugin(AptNoteAdsPlugin.class);
        super.onCreate(savedInstanceState);
    }
}
