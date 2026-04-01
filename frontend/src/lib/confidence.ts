export const CONFIDENCE_META = {
    high: {
        label: '高信頼',
        shortLabel: '高',
        chipClass: 'bg-score-high/10 text-score-high',
        description: 'judge が、ルーブリック適合と根拠の十分性を比較的明確に判断できた状態です。',
    },
    medium: {
        label: '中信頼',
        shortLabel: '中',
        chipClass: 'bg-score-mid/10 text-score-mid',
        description: '一部の評価軸や解釈に曖昧さがあり、点数は慎重に読むべき状態です。',
    },
    low: {
        label: '低信頼',
        shortLabel: '低',
        chipClass: 'bg-score-low/10 text-score-low',
        description: 'judge が十分な確信や事実根拠を持てず、手動確認の優先度が高い状態です。',
    },
} as const;

export type ConfidenceLevel = keyof typeof CONFIDENCE_META;
