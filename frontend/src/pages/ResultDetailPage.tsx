import { useParams, useNavigate } from 'react-router-dom';
import { useHistoryStore } from '../store/historyStore';
import ResultDetail from '../components/ResultDetail';
import { ArrowLeft, AlertCircle } from 'lucide-react';

export default function ResultDetailPage() {
    const { runId } = useParams<{ runId: string }>();
    const navigate = useNavigate();
    const run = useHistoryStore((s) => s.getRunById(runId || ''));

    if (!run) {
        return (
            <div className="space-y-6 animate-fade-up">
                <button
                    onClick={() => navigate(-1)}
                    className="flex items-center gap-1.5 text-[12px] text-text-secondary hover:text-amber transition-colors"
                >
                    <ArrowLeft size={14} /> Back
                </button>
                <div className="card p-12 text-center space-y-3">
                    <AlertCircle size={28} className="text-score-low mx-auto" />
                    <h2 className="text-[14px] font-display font-semibold text-text-secondary">Result not found</h2>
                    <p className="text-[12px] text-text-tertiary">Run "{runId}" may have been cleared from history.</p>
                </div>
            </div>
        );
    }

    return (
        <div className="space-y-6 animate-fade-up">
            <button
                onClick={() => navigate(-1)}
                className="flex items-center gap-1.5 text-[12px] text-text-secondary hover:text-amber transition-colors"
            >
                <ArrowLeft size={14} /> Back to Dashboard
            </button>
            <ResultDetail run={run} />
        </div>
    );
}
