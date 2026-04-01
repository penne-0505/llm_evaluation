import { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useHistoryStore } from '../store/historyStore';
import { useRunStore } from '../store/runStore';
import { deleteResult } from '../api/client';
import ResultDetail from '../components/ResultDetail';
import { ArrowLeft, AlertCircle, Trash2 } from 'lucide-react';
import { decodeResultRouteParam } from '../lib/resultRoutes';

export default function ResultDetailPage() {
    const { runId: routeRunId } = useParams<{ runId: string }>();
    const runId = decodeResultRouteParam(routeRunId);
    const navigate = useNavigate();
    const initializeHistory = useHistoryStore((s) => s.initialize);
    const loadRunDetail = useHistoryStore((s) => s.loadRunDetail);
    const getSummaryByRunId = useHistoryStore((s) => s.getSummaryByRunId);
    const removeRun = useHistoryStore((s) => s.removeRun);
    const isLoaded = useHistoryStore((s) => s.isLoaded);
    const run = useHistoryStore((s) => s.getRunById(runId || ''));
    const clearResult = useRunStore((s) => s.clearResult);
    const [isLoadingDetail, setIsLoadingDetail] = useState(false);
    const [isDeleting, setIsDeleting] = useState(false);

    useEffect(() => {
        if (!runId) return;

        let cancelled = false;

        const load = async () => {
            setIsLoadingDetail(true);
            await initializeHistory();
            if (!cancelled) {
                await loadRunDetail(runId);
            }
            if (!cancelled) {
                setIsLoadingDetail(false);
            }
        };

        void load();

        return () => {
            cancelled = true;
        };
    }, [initializeHistory, loadRunDetail, runId]);

    if (!isLoaded || isLoadingDetail) {
        return <div className="flex items-center justify-center h-64"><div className="w-5 h-5 border-2 border-amber border-t-transparent rounded-full animate-spin" /></div>;
    }

    if (!run) {
        return (
            <div className="space-y-6 animate-fade-up">
                <button
                    onClick={() => navigate(-1)}
                    className="flex items-center gap-1.5 text-[12px] text-text-secondary hover:text-amber transition-colors"
                >
                    <ArrowLeft size={14} /> 戻る
                </button>
                <div className="card p-12 text-center space-y-3">
                    <AlertCircle size={28} className="text-score-low mx-auto" />
                    <h2 className="text-[14px] font-display font-semibold text-text-secondary">結果が見つかりません</h2>
                    <p className="text-[12px] text-text-tertiary">実行 "{runId}" は履歴から削除された可能性があります。</p>
                </div>
            </div>
        );
    }

    const handleDelete = async () => {
        const summary = getSummaryByRunId(run.id);
        if (!summary?.filename) {
            window.alert('削除対象の結果ファイルを特定できませんでした。');
            return;
        }
        const confirmed = window.confirm(`この結果を削除しますか？\n${run.subjectModelName} / ${run.id}`);
        if (!confirmed) {
            return;
        }

        try {
            setIsDeleting(true);
            await deleteResult(summary.filename);
            removeRun(run.id);
            clearResult();
            navigate('/results', { replace: true });
        } catch (error) {
            window.alert(error instanceof Error ? error.message : '結果の削除に失敗しました。');
        } finally {
            setIsDeleting(false);
        }
    };

    return (
        <div className="space-y-6 animate-fade-up">
            <div className="flex items-center justify-between gap-3">
                <button
                    onClick={() => navigate(-1)}
                    className="flex items-center gap-1.5 text-[12px] text-text-secondary hover:text-amber transition-colors"
                >
                    <ArrowLeft size={14} /> ダッシュボードへ戻る
                </button>
                <button
                    onClick={() => void handleDelete()}
                    disabled={isDeleting}
                    className="inline-flex items-center gap-1.5 rounded border border-score-low/20 px-3 py-1.5 text-[12px] text-score-low transition-colors hover:border-score-low/40 hover:bg-score-low/8 disabled:opacity-40"
                >
                    <Trash2 size={13} />
                    {isDeleting ? '削除中...' : 'この結果を削除'}
                </button>
            </div>
            <ResultDetail run={run} />
        </div>
    );
}
