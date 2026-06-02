import { Component, type ErrorInfo, type ReactNode } from "react";
import { recordError } from "./crash";

type Props = {
  children: ReactNode;
};

type State = {
  hasError: boolean;
};

// React 렌더 트리에서 발생한 예외를 잡아 Crashlytics 에 비치명적으로 보고하고,
// 흰 화면 대신 복구 가능한 안내 UI 를 보여준다.
class ErrorBoundary extends Component<Props, State> {
  state: State = { hasError: false };

  static getDerivedStateFromError(): State {
    return { hasError: true };
  }

  componentDidCatch(error: Error, info: ErrorInfo): void {
    void recordError(error, {
      source: "react.errorBoundary",
      componentStack: info.componentStack ?? ""
    });
  }

  private handleReload = () => {
    // 상태만 리셋해 재렌더를 시도한다. 회복되지 않으면 사용자가 앱을 재시작하면 된다.
    this.setState({ hasError: false });
  };

  render(): ReactNode {
    if (!this.state.hasError) return this.props.children;
    return (
      <div
        role="alert"
        style={{
          minHeight: "100vh",
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          justifyContent: "center",
          gap: 16,
          padding: 24,
          textAlign: "center",
          background: "#fffaf3",
          color: "#2c2925",
          fontSize: 16,
          lineHeight: 1.5
        }}
      >
        <strong style={{ fontSize: 18 }}>일시적인 문제가 발생했어요</strong>
        <span style={{ maxWidth: 320 }}>
          잠시 후 다시 시도해 주세요. 문제가 계속되면 앱을 재시작해 주세요.
        </span>
        <button
          type="button"
          onClick={this.handleReload}
          style={{
            cursor: "pointer",
            minHeight: 44,
            padding: "12px 24px",
            borderRadius: 999,
            border: "none",
            background: "#d97757",
            color: "#fff",
            fontSize: 16,
            fontWeight: 600
          }}
        >
          다시 시도
        </button>
      </div>
    );
  }
}

export default ErrorBoundary;
