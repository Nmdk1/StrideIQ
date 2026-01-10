/**
 * Japanese Translations
 * 
 * Target market: Japan (Tokyo Marathon, Hakone Ekiden culture)
 * Tone: Polite but direct, avoiding overly formal keigo
 */

import type { TranslationKeys } from './en';

export const ja: TranslationKeys = {
  // Navigation
  nav: {
    dashboard: 'ダッシュボード',
    checkin: 'チェックイン',
    activities: 'アクティビティ',
    discovery: '発見',
    nutrition: '栄養',
    profile: 'プロフィール',
    settings: '設定',
    login: 'ログイン',
    register: '登録',
    logout: 'ログアウト',
  },
  
  // Landing page
  landing: {
    hero: {
      title: 'あなたに本当に効くものを見つける',
      subtitle: '「一般的なランナー」ではなく、あなたの体に合うものを。',
      cta: '無料で始める',
    },
    value: {
      efficiency: '体力がついているのか、疲れているだけなのか？',
      correlations: 'あなたのランニングに効くものは？私たちが見つけます。',
      personal: 'あなたのデータ。あなたのパターン。あなたの洞察。',
    },
  },
  
  // Dashboard
  dashboard: {
    title: '効率ダッシュボード',
    subtitle: '体力がついているのか、ただ疲労を蓄積しているのか？',
    noData: 'ペースと心拍数のある3つ以上のアクティビティが必要です。',
    timeRange: {
      '30': '過去30日',
      '60': '過去60日',
      '90': '過去90日',
      '180': '過去6ヶ月',
      '365': '過去1年',
    },
  },
  
  // Check-in
  checkin: {
    title: 'チェックイン',
    sleep: '睡眠',
    stress: 'ストレス',
    soreness: '筋肉痛',
    hrv: 'HRV',
    restingHr: '安静時心拍',
    optional: '任意',
    submit: '完了',
    skip: '今日はスキップ',
    success: '記録しました。',
    labels: {
      sleepLow: '0時間',
      sleepHigh: '12時間',
      stressLow: '低い',
      stressHigh: '高い',
      sorenessLow: 'フレッシュ',
      sorenessHigh: 'とても痛い',
    },
  },
  
  // Discovery / Correlations
  discovery: {
    title: 'あなたに効くもの',
    whatWorks: '効果あり',
    whatDoesnt: '効果なし',
    noData: 'まだデータが不足しています。2〜3週間記録を続けてください。',
    correlation: {
      strong: '強いパターン',
      moderate: '中程度のパターン',
      weak: '弱いパターン',
    },
  },
  
  // Nutrition
  nutrition: {
    title: '栄養',
    addMeal: '食事を追加',
    logFood: '何を食べましたか？',
    when: 'いつ',
    notes: 'メモ',
    placeholder: '例：オートミールとバナナ、ブラックコーヒー',
  },
  
  // Activities
  activities: {
    title: 'アクティビティ',
    noActivities: 'まだアクティビティが同期されていません',
    connectStrava: 'Stravaに接続',
    pace: 'ペース',
    heartRate: '心拍',
    efficiency: '効率',
  },
  
  // Profile
  profile: {
    title: 'プロフィール',
    personalInfo: '個人情報',
    metrics: 'あなたの指標',
    age: '年齢',
    weight: '体重',
    height: '身長',
  },
  
  // Settings
  settings: {
    title: '設定',
    integrations: '連携',
    preferences: '設定',
    privacy: 'プライバシー',
    exportData: 'データをエクスポート',
    deleteAccount: 'アカウントを削除',
  },
  
  // Auth
  auth: {
    login: 'ログイン',
    register: 'アカウント作成',
    email: 'メールアドレス',
    password: 'パスワード',
    forgotPassword: 'パスワードを忘れた？',
    noAccount: 'アカウントをお持ちでない？',
    hasAccount: 'すでにアカウントをお持ち？',
  },
  
  // Educational / Onboarding
  education: {
    whyLog: {
      title: 'なぜ記録するのか？',
      reason: '記録すればするほど、より多くのパターンを見つけられます。',
    },
    dataQuality: {
      title: 'データ品質',
      ready: '洞察の準備完了',
      building: 'パターンを構築中...',
    },
    emptyStates: {
      nutrition: {
        title: 'まだ食事が記録されていません',
        description: '食事を記録すると、次のようなパターンを見つけられます：',
        example: '「ランニング2時間前に炭水化物を摂ると、ペースが3%向上する」',
        cta: '食事を記録',
      },
      checkin: {
        title: 'まだチェックインがありません',
        description: '5秒のモーニングチェックインで、次のようなパターンを見つけられます：',
        example: '「7時間以上睡眠を取ると、8%速く走れる」',
        cta: 'クイックチェックイン',
      },
      correlations: {
        title: 'まだ相関を分析するのに十分なデータがありません',
        description: 'あなたに効くものを見つけるには、2〜3週間の記録が必要です。',
      },
    },
  },
  
  // Common
  common: {
    save: '保存',
    cancel: 'キャンセル',
    delete: '削除',
    edit: '編集',
    loading: '読み込み中...',
    error: '問題が発生しました',
    retry: '再試行',
    next: '次へ',
    back: '戻る',
    skip: 'スキップ',
    done: '完了',
  },
  
  // Units
  units: {
    km: 'km',
    mi: 'mi',
    kg: 'kg',
    lb: 'lb',
    cm: 'cm',
    ft: 'ft',
    bpm: 'bpm',
    hours: '時間',
    minutes: '分',
    seconds: '秒',
  },
};


