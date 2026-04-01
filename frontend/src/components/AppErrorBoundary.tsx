import { Component, type ErrorInfo, type ReactNode } from 'react';
import { AlertCircle } from 'lucide-react';

interface Props {
    children: ReactNode;
}

interface State {
    hasError: boolean;
    message: string;
}

async function reportClientError(payload: {
    source: string;
    message: string;
    stack?: string;
    path?: string;
}) {
    try {
        await fetch('/api/client-errors', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload),
        });
    } catch {
        // クライアント側ログ送信失敗は握り潰す
    }
}

export default class AppErrorBoundary extends Component<Props, State> {
    state: State = {
        hasError: false,
        message: '',
    };

    static getDerivedStateFromError(error: Error): State {
        return {
            hasError: true,
            message: error.message || '不明なクライアントエラー',
        };
    }

    componentDidCatch(error: Error, errorInfo: ErrorInfo) {
        void reportClientError({
            source: 'react_error_boundary',
            message: error.message || '不明なクライアントエラー',
            stack: [error.stack, errorInfo.componentStack].filter(Boolean).join('\n\n'),
            path: window.location.pathname,
        });
    }

    render() {
        if (!this.state.hasError) {
            return this.props.children;
        }

        return (
            <div className="min-h-screen bg-bg text-text-primary flex items-center justify-center px-6">
                <div className="card max-w-xl w-full p-8 text-center space-y-4">
                    <AlertCircle size={32} className="text-score-low mx-auto" />
                    <h1 className="text-[16px] font-display font-semibold">クライアント実行時エラー</h1>
                    <p className="text-[13px] text-text-secondary">
                        画面描画中にフロントエンド例外が発生しました。詳細は `app.log` に送信済みです。
                    </p>
                    <p className="text-[12px] text-text-tertiary break-all">{this.state.message}</p>
                    <button
                        onClick={() => window.location.reload()}
                        className="px-4 py-2 rounded-md bg-amber text-bg text-[12px] font-display font-semibold hover:bg-amber-hover transition-colors"
                    >
                        再読み込み
                    </button>
                </div>
            </div>
        );
    }
}
