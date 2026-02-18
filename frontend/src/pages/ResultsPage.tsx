import { useRunStore } from '../store/runStore';
import { useHistoryStore } from '../store/historyStore';
import ResultDetail from '../components/ResultDetail';
import { BarChart3 } from 'lucide-react';

export default function ResultsPage() {
    const runResult = useRunStore((s) => s.result);
    const latestHistory = useHistoryStore((s) => s.runs[0]);
    const result = runResult || latestHistory;

    if (!result) {
        return (
            <div className="space-y-6 animate-fade-up">
                <div className="hero-glow relative py-2">
                    <div className="relative z-10">
                        <p className="section-label mb-2">Readout</p>
                        <h1 className="text-2xl font-display font-bold text-text-primary tracking-tight">Results</h1>
                        <p className="text-text-secondary mt-1 text-[13px]">Latest evaluation output</p>
                    </div>
                </div>
                <div className="card p-12 text-center space-y-3">
                    <BarChart3 size={28} className="text-text-tertiary mx-auto" />
                    <h2 className="text-[14px] font-display font-semibold text-text-secondary">No results yet</h2>
                    <p className="text-[12px] text-text-tertiary max-w-md mx-auto">
                        Run an evaluation to see results here, or check the Dashboard for historical data.
                    </p>
                </div>
            </div>
        );
    }

    return (
        <div className="space-y-6">
            <div className="hero-glow relative py-2 animate-fade-up">
                <div className="relative z-10">
                    <p className="section-label mb-2">Readout</p>
                    <h1 className="text-2xl font-display font-bold text-text-primary tracking-tight">Results</h1>
                    <p className="text-text-secondary mt-1 text-[13px]">Latest evaluation output</p>
                </div>
            </div>
            <ResultDetail run={result} />
        </div>
    );
}
