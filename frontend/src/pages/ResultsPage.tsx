import { useEffect, useState } from 'react';
import { useRunStore } from '../store/runStore';
import { useHistoryStore } from '../store/historyStore';
import { deleteResult } from '../api/client';
import ResultDetail from '../components/ResultDetail';
import { BarChart3, Trash2 } from 'lucide-react';

export default function ResultsPage() {
    const runResult = useRunStore((s) => s.result);
    const resultFilePath = useRunStore((s) => s.resultFilePath);
    const clearResult = useRunStore((s) => s.clearResult);
    const initializeHistory = useHistoryStore((s) => s.initialize);
    const isLoaded = useHistoryStore((s) => s.isLoaded);
    const loadError = useHistoryStore((s) => s.loadError);
    const latestHistory = useHistoryStore((s) => s.runs[0]);
    const getSummaryByRunId = useHistoryStore((s) => s.getSummaryByRunId);
    const removeRun = useHistoryStore((s) => s.removeRun);
    const result = runResult || latestHistory;
    const [isDeleting, setIsDeleting] = useState(false);

    useEffect(() => {
        if (!runResult) {
            void initializeHistory();
        }
    }, [initializeHistory, runResult]);

    if (!runResult && !isLoaded) {
        return <div className="flex items-center justify-center h-64"><div className="w-5 h-5 border-2 border-amber border-t-transparent rounded-full animate-spin" /></div>;
    }

    if (loadError && !result) {
        return (
            <div className="card p-12 text-center space-y-3">
                <BarChart3 size={28} className="text-score-low mx-auto" />
                <h2 className="text-[14px] font-display font-semibold text-text-secondary">結果の読み込みに失敗しました</h2>
                <p className="text-[12px] text-text-tertiary max-w-md mx-auto">{loadError}</p>
            </div>
        );
    }

    if (!result) {
        return (
            <div className="space-y-6 animate-fade-up">
                <div className="hero-glow relative py-2">
                    <div className="relative z-10">
                        <p className="section-label mb-2">結果表示</p>
                        <h1 className="text-2xl font-display font-bold text-text-primary tracking-tight">結果</h1>
                        <p className="text-text-secondary mt-1 text-[13px]">最新の評価結果を表示します</p>
                    </div>
                </div>
                <div className="card p-12 text-center space-y-3">
                    <BarChart3 size={28} className="text-text-tertiary mx-auto" />
                    <h2 className="text-[14px] font-display font-semibold text-text-secondary">まだ結果がありません</h2>
                    <p className="text-[12px] text-text-tertiary max-w-md mx-auto">
                        評価を実行するとここに結果が表示されます。過去の履歴はダッシュボードでも確認できます。
                    </p>
                </div>
            </div>
        );
    }

    const resolveFilename = (): string | null => {
        const summary = getSummaryByRunId(result.id);
        if (summary?.filename) {
            return summary.filename;
        }
        if (runResult?.id === result.id && resultFilePath) {
            const parts = resultFilePath.split(/[\\/]/);
            return parts[parts.length - 1] || null;
        }
        return null;
    };

    const handleDelete = async () => {
        const filename = resolveFilename();
        if (!filename) {
            window.alert('削除対象の結果ファイルを特定できませんでした。');
            return;
        }
        const confirmed = window.confirm(`この結果を削除しますか？\n${result.subjectModelName} / ${result.id}`);
        if (!confirmed) {
            return;
        }
        try {
            setIsDeleting(true);
            await deleteResult(filename);
            removeRun(result.id);
            if (runResult?.id === result.id) {
                clearResult();
            }
        } catch (error) {
            window.alert(error instanceof Error ? error.message : '結果の削除に失敗しました。');
        } finally {
            setIsDeleting(false);
        }
    };

    return (
        <div className="space-y-6">
            <div className="hero-glow relative py-2 animate-fade-up">
                <div className="relative z-10 flex items-start justify-between gap-4">
                    <div>
                        <p className="section-label mb-2">結果表示</p>
                        <h1 className="text-2xl font-display font-bold text-text-primary tracking-tight">結果</h1>
                        <p className="text-text-secondary mt-1 text-[13px]">最新の評価結果を表示します</p>
                    </div>
                    <button
                        onClick={() => void handleDelete()}
                        disabled={isDeleting}
                        className="inline-flex items-center gap-1.5 rounded border border-score-low/20 px-3 py-1.5 text-[12px] text-score-low transition-colors hover:border-score-low/40 hover:bg-score-low/8 disabled:opacity-40"
                    >
                        <Trash2 size={13} />
                        {isDeleting ? '削除中...' : 'この結果を削除'}
                    </button>
                </div>
            </div>
            <ResultDetail run={result} />
        </div>
    );
}
