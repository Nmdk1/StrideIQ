'use client';

import { useState, useRef, useCallback, useEffect, useMemo } from 'react';
import { ProtectedRoute } from '@/components/auth/ProtectedRoute';
import { useAuth } from '@/lib/hooks/useAuth';
import {
  useNutritionEntries,
  useCreateNutritionEntry,
  useDeleteNutritionEntry,
  useUpdateNutritionEntry,
  useParseNutritionText,
  useNLParsingAvailable,
  useParsePhoto,
  useFuelingProducts,
  useFuelingProfile,
  useAddToProfile,
  useRemoveFromProfile,
  useLogFueling,
  useScanBarcode,
  useNutritionSummary,
  useActivityLinkedNutrition,
  useNutritionGoal,
  useUpsertNutritionGoal,
  useDailyTarget,
  useMealTemplates,
  useCreateMealTemplate,
  useDeleteMealTemplate,
  useUpdateMealTemplate,
  useLogMealTemplate,
  useParseMealItems,
} from '@/lib/hooks/queries/nutrition';
import type { MealTemplate, MealTemplateItem } from '@/lib/api/services/nutrition';
import { LoadingSpinner } from '@/components/ui/LoadingSpinner';
import { nutritionService } from '@/lib/api/services/nutrition';
import type { NutritionEntryCreate, DaySummary } from '@/lib/api/services/nutrition';

type ActiveTab = 'log' | 'meals' | 'history' | 'insights';

function macroSourceBadge(source: string | undefined) {
  if (!source) return null;
  let label: string;
  let cls: string;
  switch (source) {
    case 'usda_local':
    case 'usda_api':
      label = 'USDA';
      cls = 'bg-green-900/50 text-green-400 border-green-700/40';
      break;
    case 'branded_barcode':
    case 'openfoodfacts':
      label = 'Verified';
      cls = 'bg-blue-900/50 text-blue-400 border-blue-700/40';
      break;
    case 'llm_estimated':
      label = 'Estimated';
      cls = 'bg-amber-900/50 text-amber-400 border-amber-700/40';
      break;
    case 'product_library':
      label = 'Product';
      cls = 'bg-purple-900/50 text-purple-400 border-purple-700/40';
      break;
    case 'template':
      label = 'Template';
      cls = 'bg-teal-900/50 text-teal-400 border-teal-700/40';
      break;
    default:
      return null;
  }
  return (
    <span className={`inline-block text-[10px] font-medium px-1.5 py-0.5 rounded border ${cls}`}>
      {label}
    </span>
  );
}

function formatDateShort(dateStr: string): string {
  const d = new Date(dateStr + 'T12:00:00');
  return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
}

function shiftDate(dateStr: string, delta: number): string {
  const d = new Date(dateStr + 'T12:00:00');
  d.setDate(d.getDate() + delta);
  return d.toISOString().split('T')[0];
}

function TrendChart({ days }: { days: DaySummary[] }) {
  const logged = days.filter((d) => d.entry_count > 0);
  if (logged.length < 2) {
    return (
      <div className="bg-slate-700 rounded-lg h-[200px] flex items-center justify-center">
        <p className="text-xs text-slate-500">Need at least 2 logged days to show a trend</p>
      </div>
    );
  }

  const width = 358;
  const height = 200;
  const px = 32;
  const py = 24;
  const plotW = width - px * 2;
  const plotH = height - py * 2;

  const allDates = days.map((d) => d.date);
  const minDate = allDates[0];
  const maxDate = allDates[allDates.length - 1];
  const daySpan = Math.max(1, Math.round((new Date(maxDate).getTime() - new Date(minDate).getTime()) / 86400000));

  const maxCal = Math.max(...logged.map((d) => d.calories), 1);
  const yTop = Math.ceil(maxCal / 500) * 500;

  const points = logged.map((d) => {
    const dayIdx = Math.round((new Date(d.date).getTime() - new Date(minDate).getTime()) / 86400000);
    const x = px + (dayIdx / daySpan) * plotW;
    const y = py + plotH - (d.calories / yTop) * plotH;
    return { x, y, cal: d.calories, date: d.date };
  });

  const pathD = points.map((p, i) => `${i === 0 ? 'M' : 'L'}${p.x.toFixed(1)},${p.y.toFixed(1)}`).join(' ');

  const gridLines = [];
  for (let v = 0; v <= yTop; v += 500) {
    const y = py + plotH - (v / yTop) * plotH;
    gridLines.push({ y, label: v.toString() });
  }

  return (
    <svg viewBox={`0 0 ${width} ${height}`} className="w-full bg-slate-700 rounded-lg" preserveAspectRatio="xMidYMid meet">
      {gridLines.map((g) => (
        <g key={g.label}>
          <line x1={px} y1={g.y} x2={width - px} y2={g.y} stroke="#475569" strokeWidth={0.5} strokeDasharray="4 4" />
          <text x={px - 4} y={g.y + 3} textAnchor="end" className="fill-slate-500" fontSize={9}>{g.label}</text>
        </g>
      ))}
      <path d={pathD} fill="none" stroke="#60a5fa" strokeWidth={2} strokeLinejoin="round" strokeLinecap="round" />
      {points.map((p) => (
        <circle key={p.date} cx={p.x} cy={p.y} r={3.5} fill="#60a5fa" stroke="#1e293b" strokeWidth={1.5} />
      ))}
    </svg>
  );
}

export default function NutritionPage() {
  const { user } = useAuth();
  const today = new Date().toISOString().split('T')[0];

  const [activeTab, setActiveTab] = useState<ActiveTab>('log');
  const [selectedDate, setSelectedDate] = useState(today);

  // Date that all entry-create flows should target. On the History tab the user
  // can pick any past day; everywhere else this stays today. Single source of
  // truth so Photo / Scan / NL parse / Shelf / Type-it can all backfill.
  const entryDate = activeTab === 'history' ? selectedDate : today;
  const isBackfill = entryDate !== today;

  const { data: entries, isLoading } = useNutritionEntries({ start_date: today, end_date: today });
  const { data: nlAvailable } = useNLParsingAvailable();
  const { data: shelfItems } = useFuelingProfile();
  const { data: allProducts } = useFuelingProducts();
  const createEntry = useCreateNutritionEntry();
  const deleteEntry = useDeleteNutritionEntry();
  const updateEntry = useUpdateNutritionEntry();
  const parseText = useParseNutritionText();
  const parsePhoto = useParsePhoto();
  const logFueling = useLogFueling();
  const scanBarcode = useScanBarcode();
  const addToProfile = useAddToProfile();
  const removeFromProfile = useRemoveFromProfile();

  const { data: historyEntries } = useNutritionEntries({ start_date: selectedDate, end_date: selectedDate });
  const { data: summary7 } = useNutritionSummary(7);
  const { data: summary30 } = useNutritionSummary(30);
  const { data: activityLinked } = useActivityLinkedNutrition(30);

  const { data: nutritionGoal } = useNutritionGoal();
  const upsertGoal = useUpsertNutritionGoal();
  const { data: dailyTarget } = useDailyTarget();
  const { data: historyTarget } = useDailyTarget(selectedDate !== today ? selectedDate : undefined);

  const { data: meals } = useMealTemplates();
  const createMeal = useCreateMealTemplate();
  const deleteMeal = useDeleteMealTemplate();
  const updateMeal = useUpdateMealTemplate();
  const logMeal = useLogMealTemplate();
  const [showMealForm, setShowMealForm] = useState(false);
  const [mealForm, setMealForm] = useState<{ name: string; items: MealTemplateItem[] }>({
    name: '',
    items: [{ food: '', calories: undefined, protein_g: undefined, carbs_g: undefined, fat_g: undefined }],
  });
  const [editingMealId, setEditingMealId] = useState<number | null>(null);
  const parseMealItems = useParseMealItems();
  const [mealParseText, setMealParseText] = useState('');

  const [showGoalSetup, setShowGoalSetup] = useState(false);
  const [goalForm, setGoalForm] = useState({
    goal_type: 'performance' as 'performance' | 'maintain' | 'recomp',
    protein_g_per_kg: 1.8,
    carb_pct: 0.55,
    fat_pct: 0.45,
    caffeine_target_mg: undefined as number | undefined,
    load_adaptive: true,
  });

  useEffect(() => {
    if (nutritionGoal) {
      setGoalForm({
        goal_type: nutritionGoal.goal_type,
        protein_g_per_kg: nutritionGoal.protein_g_per_kg,
        carb_pct: nutritionGoal.carb_pct ?? 0.55,
        fat_pct: nutritionGoal.fat_pct ?? 0.45,
        caffeine_target_mg: nutritionGoal.caffeine_target_mg ?? undefined,
        load_adaptive: nutritionGoal.load_adaptive,
      });
    }
  }, [nutritionGoal]);

  const [showForm, setShowForm] = useState(false);
  const [nlText, setNlText] = useState('');
  const [toast, setToast] = useState<string | null>(null);
  const [photoPreview, setPhotoPreview] = useState<string | null>(null);
  const [photoItems, setPhotoItems] = useState<Array<{
    food: string; grams: number; calories: number;
    protein_g: number; carbs_g: number; fat_g: number; fiber_g: number;
    macro_source: string; fdc_id?: number;
  }> | null>(null);
  const [barcodeResult, setBarcodeResult] = useState<{
    food_name: string; calories: number; protein_g: number;
    carbs_g: number; fat_g: number; servings: number; fdc_id?: number;
    upc?: string; is_athlete_override?: boolean;
  } | null>(null);
  const [templateMatch, setTemplateMatch] = useState<{
    meal_signature: string; items: Record<string, unknown>[]; times_confirmed: number;
  } | null>(null);
  const [showCatalog, setShowCatalog] = useState(false);
  const [catalogSearch, setCatalogSearch] = useState('');
  const [catalogCategory, setCatalogCategory] = useState<string>('');
  const [scannerOpen, setScannerOpen] = useState(false);
  const [scannerLoading, setScannerLoading] = useState(false);
  const [formData, setFormData] = useState<NutritionEntryCreate>({
    athlete_id: user?.id || '',
    date: today,
    entry_type: 'daily',
    calories: undefined,
    protein_g: undefined,
    carbs_g: undefined,
    fat_g: undefined,
    fiber_g: undefined,
    notes: '',
  });

  const [editingEntryId, setEditingEntryId] = useState<string | null>(null);
  const [editForm, setEditForm] = useState<{
    calories?: number; protein_g?: number; carbs_g?: number; fat_g?: number; notes?: string;
  }>({});

  const photoRef = useRef<HTMLInputElement>(null);
  const scannerRef = useRef<unknown>(null);

  const shelfProductIds = new Set(shelfItems?.map((s) => s.product_id) || []);

  const filteredCatalog = (allProducts || []).filter((p) => {
    if (catalogCategory && p.category !== catalogCategory) return false;
    if (catalogSearch) {
      const q = catalogSearch.toLowerCase();
      return (
        p.brand.toLowerCase().includes(q) ||
        p.product_name.toLowerCase().includes(q) ||
        (p.variant || '').toLowerCase().includes(q)
      );
    }
    return true;
  });

  const showToast = useCallback((msg: string) => {
    setToast(msg);
    setTimeout(() => setToast(null), 3000);
  }, []);

  const handleSaveGoal = async () => {
    try {
      await upsertGoal.mutateAsync({
        goal_type: goalForm.goal_type,
        protein_g_per_kg: goalForm.protein_g_per_kg,
        carb_pct: goalForm.carb_pct,
        fat_pct: goalForm.fat_pct,
        caffeine_target_mg: goalForm.caffeine_target_mg,
        load_adaptive: goalForm.load_adaptive,
      });
      setShowGoalSetup(false);
      showToast('Goal saved');
    } catch {
      showToast('Failed to save goal');
    }
  };

  const totals = entries?.reduce(
    (acc, e) => ({
      cal: acc.cal + (e.calories || 0),
      protein: acc.protein + (e.protein_g || 0),
      carbs: acc.carbs + (e.carbs_g || 0),
      fat: acc.fat + (e.fat_g || 0),
      caffeine: acc.caffeine + (e.caffeine_mg || 0),
    }),
    { cal: 0, protein: 0, carbs: 0, fat: 0, caffeine: 0 },
  ) || { cal: 0, protein: 0, carbs: 0, fat: 0, caffeine: 0 };

  const historyTotals = useMemo(() => {
    if (!historyEntries?.length) return { cal: 0, protein: 0, carbs: 0, fat: 0, caffeine: 0 };
    return historyEntries.reduce(
      (acc, e) => ({
        cal: acc.cal + (e.calories || 0),
        protein: acc.protein + (e.protein_g || 0),
        carbs: acc.carbs + (e.carbs_g || 0),
        fat: acc.fat + (e.fat_g || 0),
        caffeine: acc.caffeine + (e.caffeine_mg || 0),
      }),
      { cal: 0, protein: 0, carbs: 0, fat: 0, caffeine: 0 },
    );
  }, [historyEntries]);

  const handlePhotoCapture = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setPhotoPreview(URL.createObjectURL(file));
    setPhotoItems(null);
    setTemplateMatch(null);
    try {
      const result = await parsePhoto.mutateAsync(file);
      setPhotoItems(result.items);
      if (result.template_match && result.template_match.times_confirmed >= 3) {
        setTemplateMatch(result.template_match);
      }
    } catch {
      showToast('Photo analysis failed. Try again or type it instead.');
      setPhotoPreview(null);
    }
  };

  const handleConfirmPhoto = async () => {
    if (!photoItems?.length) return;
    const totalCal = photoItems.reduce((s, i) => s + i.calories, 0);
    const totalP = photoItems.reduce((s, i) => s + i.protein_g, 0);
    const totalC = photoItems.reduce((s, i) => s + i.carbs_g, 0);
    const totalF = photoItems.reduce((s, i) => s + i.fat_g, 0);
    const totalFib = photoItems.reduce((s, i) => s + i.fiber_g, 0);
    const notes = photoItems.map((i) => `${i.food} (${i.grams}g)`).join(', ');
    const primarySource = photoItems[0]?.macro_source || 'llm_estimated';

    try {
      await createEntry.mutateAsync({
        athlete_id: user?.id || '',
        date: entryDate,
        entry_type: 'daily',
        calories: Math.round(totalCal),
        protein_g: Math.round(totalP),
        carbs_g: Math.round(totalC),
        fat_g: Math.round(totalF),
        fiber_g: Math.round(totalFib),
        notes,
        macro_source: primarySource,
      });
      showToast(isBackfill ? `Logged to ${formatDateShort(entryDate)}` : 'Meal logged');
      setPhotoPreview(null);
      setPhotoItems(null);
      setTemplateMatch(null);
    } catch {
      showToast('Failed to save. Try again.');
    }
  };

  const stopScanner = useCallback(async () => {
    try {
      const scanner = scannerRef.current as { getState?: () => number; stop: () => Promise<void>; clear: () => Promise<void> };
      if (scanner) {
        const state = scanner.getState?.();
        if (state === 2) await scanner.stop();
        await scanner.clear();
        scannerRef.current = null;
      }
    } catch { /* scanner may already be stopped */ }
    setScannerOpen(false);
    setScannerLoading(false);
  }, []);

  const startScanner = useCallback(async () => {
    setScannerOpen(true);
    setScannerLoading(true);
    try {
      const { Html5Qrcode } = await import('html5-qrcode');

      // Wait for the DOM element to render
      await new Promise((r) => setTimeout(r, 300));
      if (!document.getElementById('barcode-live-reader')) {
        throw new Error('Scanner container not found');
      }

      const scanner = new Html5Qrcode('barcode-live-reader', { verbose: false });
      scannerRef.current = scanner;

      const onScanSuccess = async (decodedText: string) => {
        try {
          const state = (scanner as unknown as { getState?: () => number }).getState?.();
          if (state === 2) await scanner.stop();
        } catch { /* ignore */ }
        await scanner.clear();
        scannerRef.current = null;
        setScannerOpen(false);
        setScannerLoading(false);

        try {
          const scan = await scanBarcode.mutateAsync(decodedText);
          if (scan.found && scan.food_name) {
            setBarcodeResult({
              food_name: scan.food_name,
              calories: scan.calories || 0,
              protein_g: scan.protein_g || 0,
              carbs_g: scan.carbs_g || 0,
              fat_g: scan.fat_g || 0,
              servings: 1,
              fdc_id: scan.fdc_id,
              upc: scan.upc || decodedText,
              is_athlete_override: scan.is_athlete_override,
            });
          } else {
            showToast('Product not found — try a photo instead');
          }
        } catch {
          showToast('Lookup failed — try again');
        }
      };

      const scanConfig = { fps: 10, qrbox: { width: 280, height: 120 } };

      // Use the library's camera enumeration which properly handles
      // permission prompts on mobile browsers
      const cameras = await Html5Qrcode.getCameras();
      if (cameras.length === 0) throw new Error('No camera found on this device');

      // Prefer back/rear camera, fall back to first available
      const backCam = cameras.find(
        (c) => /back|rear|environment/i.test(c.label),
      );
      const cameraId = backCam ? backCam.id : cameras[cameras.length - 1].id;

      await scanner.start(cameraId, scanConfig, onScanSuccess, () => {});
      setScannerLoading(false);
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Could not access camera';
      showToast(msg);
      setScannerOpen(false);
      setScannerLoading(false);
    }
  }, [scanBarcode, showToast]);

  useEffect(() => {
    return () => { stopScanner(); };
  }, [stopScanner]);

  const handleConfirmBarcode = async () => {
    if (!barcodeResult) return;
    const s = barcodeResult.servings;
    try {
      await createEntry.mutateAsync({
        athlete_id: user?.id || '',
        date: entryDate,
        entry_type: 'daily',
        calories: Math.round(barcodeResult.calories * s),
        protein_g: Math.round(barcodeResult.protein_g * s),
        carbs_g: Math.round(barcodeResult.carbs_g * s),
        fat_g: Math.round(barcodeResult.fat_g * s),
        notes: barcodeResult.food_name,
        macro_source: 'branded_barcode',
        source_upc: barcodeResult.upc,
        source_fdc_id: barcodeResult.fdc_id,
      });
      showToast(isBackfill ? `Logged to ${formatDateShort(entryDate)}` : 'Logged');
      setBarcodeResult(null);
    } catch {
      showToast('Failed to save');
    }
  };

  const handleShelfTap = async (productId: number, productName: string) => {
    try {
      await logFueling.mutateAsync({
        product_id: productId,
        entry_type: 'daily',
        // Backend defaults to today when omitted; always send so backfill works.
        // Field is `entry_date` (not `date`) because the Pydantic schema avoids
        // shadowing the imported `date` type.
        entry_date: entryDate,
      });
      showToast(
        isBackfill
          ? `Logged: ${productName} → ${formatDateShort(entryDate)}`
          : `Logged: ${productName}`,
      );
    } catch {
      showToast('Failed to log');
    }
  };

  const handleParse = async (e: React.FormEvent) => {
    e.preventDefault();
    const text = nlText.trim();
    if (!text) return;
    try {
      const draft = await parseText.mutateAsync(text);
      setFormData((prev) => ({
        ...prev,
        athlete_id: user?.id || draft.athlete_id || prev.athlete_id,
        // Always use the active entry date (today on Today tab, selected day on
        // History tab). The parser returns athlete-local today which would
        // silently break past-day logging.
        date: entryDate,
        entry_type: draft.entry_type || prev.entry_type,
        calories: draft.calories,
        protein_g: draft.protein_g,
        carbs_g: draft.carbs_g,
        fat_g: draft.fat_g,
        fiber_g: draft.fiber_g,
        notes: draft.notes || text,
        macro_source: draft.macro_source,
      }));
      setShowForm(true);
    } catch {
      /* mutation state shows error */
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await createEntry.mutateAsync(formData);
      showToast(formData.date && formData.date !== today ? `Logged to ${formatDateShort(formData.date)}` : 'Logged');
      setShowForm(false);
      setFormData({
        athlete_id: user?.id || '',
        date: today,
        entry_type: 'daily',
        calories: undefined,
        protein_g: undefined,
        carbs_g: undefined,
        fat_g: undefined,
        fiber_g: undefined,
        notes: '',
      });
    } catch {
      /* mutation state shows error */
    }
  };

  const removePhotoItem = (idx: number) => {
    if (!photoItems) return;
    setPhotoItems(photoItems.filter((_, i) => i !== idx));
  };

  const adjustPortion = (idx: number, delta: number) => {
    if (!photoItems) return;
    setPhotoItems(photoItems.map((item, i) => {
      if (i !== idx) return item;
      const oldGrams = item.grams;
      const newGrams = Math.max(5, oldGrams + delta);
      const ratio = newGrams / oldGrams;
      return {
        ...item,
        grams: newGrams,
        calories: item.calories * ratio,
        protein_g: item.protein_g * ratio,
        carbs_g: item.carbs_g * ratio,
        fat_g: item.fat_g * ratio,
        fiber_g: item.fiber_g * ratio,
      };
    }));
  };

  const handleDeleteEntry = async (id: string) => {
    try {
      await deleteEntry.mutateAsync(id);
      setEditingEntryId(null);
      showToast('Entry deleted');
    } catch {
      showToast('Failed to delete');
    }
  };

  const startEditing = (entry: { id: string; calories?: number | null; protein_g?: number | null; carbs_g?: number | null; fat_g?: number | null; notes?: string | null }) => {
    setEditingEntryId(entry.id);
    setEditForm({
      calories: entry.calories ?? undefined,
      protein_g: entry.protein_g ?? undefined,
      carbs_g: entry.carbs_g ?? undefined,
      fat_g: entry.fat_g ?? undefined,
      notes: entry.notes ?? '',
    });
  };

  const handleSaveEdit = async () => {
    if (!editingEntryId) return;
    try {
      await updateEntry.mutateAsync({ id: editingEntryId, updates: editForm });
      setEditingEntryId(null);
      showToast('Entry updated');
    } catch {
      showToast('Failed to update');
    }
  };

  const handleHistorySaveEdit = async () => {
    if (!editingEntryId) return;
    try {
      // Send the selected date so the entry stays attached to the day being viewed,
      // even if the user navigates dates after opening the editor.
      await updateEntry.mutateAsync({
        id: editingEntryId,
        updates: { ...editForm, date: selectedDate },
      });
      setEditingEntryId(null);
      showToast('Entry updated');
    } catch (err) {
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      showToast(detail || 'Failed to update');
    }
  };

  const [exporting, setExporting] = useState(false);
  const handleExportCsv = async () => {
    setExporting(true);
    try {
      const endDate = today;
      const startDate = shiftDate(today, -90);
      await nutritionService.exportCsv(startDate, endDate);
      showToast('CSV downloaded');
    } catch {
      showToast('Export failed');
    } finally {
      setExporting(false);
    }
  };

  if (isLoading) {
    return (
      <ProtectedRoute>
        <div className="min-h-screen flex items-center justify-center bg-slate-900">
          <LoadingSpinner size="lg" />
        </div>
      </ProtectedRoute>
    );
  }

  return (
    <ProtectedRoute>
      <div className="min-h-screen bg-slate-900 text-slate-100">
        <div className="max-w-lg mx-auto px-4 py-6 space-y-4">

          {/* Tab Bar */}
          <div className="flex bg-slate-800 rounded-xl border border-slate-700/50 p-1 gap-1">
            {([['log', 'Log'], ['meals', 'Meals'], ['history', 'History'], ['insights', 'Insights']] as const).map(([key, label]) => (
              <button
                key={key}
                onClick={() => setActiveTab(key)}
                className={`flex-1 py-2.5 text-sm font-medium rounded-lg transition-colors min-h-[44px] ${
                  activeTab === key
                    ? 'bg-blue-600 text-white'
                    : 'text-slate-400 hover:text-slate-200 active:bg-slate-700'
                }`}
              >
                {label}
              </button>
            ))}
          </div>

          {/* Toast */}
          {toast && (
            <div className="fixed top-4 left-1/2 -translate-x-1/2 z-50 bg-green-800/90 text-green-100 px-4 py-2 rounded-lg text-sm shadow-lg">
              {toast}
            </div>
          )}

          {/* Hidden photo capture input — must live at root so it stays mounted
              across tabs. Both Today and History trigger photoRef.current.click(). */}
          <input
            ref={photoRef}
            type="file"
            accept="image/*"
            capture="environment"
            className="hidden"
            onChange={handlePhotoCapture}
          />

          {/* Manual / NL-parse entry form. Mounted at root so the same form
              works whether the user opened it from the Today or History tab.
              The form's own date picker defaults to entryDate when opened. */}
          {showForm && (activeTab === 'log' || activeTab === 'history') && (
            <div className="bg-slate-800 rounded-xl border border-slate-700/50 p-4 space-y-4">
              {isBackfill && (
                <div className="text-xs text-amber-300 bg-amber-900/20 border border-amber-700/30 rounded px-2 py-1">
                  Adding to {formatDateShort(entryDate)} (backfill)
                </div>
              )}
              {nlAvailable?.available && (
                <form onSubmit={handleParse}>
                  <label className="block text-sm font-medium mb-2">Describe what you ate</label>
                  <div className="flex gap-2">
                    <input
                      value={nlText}
                      onChange={(e) => setNlText(e.target.value)}
                      className="flex-1 px-3 py-2 bg-slate-900 border border-slate-700/50 rounded-lg text-white text-sm min-h-[44px]"
                      placeholder='"oatmeal and black coffee"'
                    />
                    <button
                      type="submit"
                      disabled={parseText.isPending || !nlText.trim()}
                      className="px-4 py-2 bg-slate-700 hover:bg-slate-600 disabled:bg-slate-800 disabled:cursor-not-allowed rounded-lg text-slate-200 text-sm font-medium min-h-[44px]"
                    >
                      {parseText.isPending ? <LoadingSpinner size="sm" /> : 'Parse'}
                    </button>
                  </div>
                </form>
              )}

              <form onSubmit={handleSubmit} className="space-y-3">
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="block text-xs font-medium mb-1 text-slate-400">Type</label>
                    <select
                      value={formData.entry_type}
                      onChange={(e) => setFormData({ ...formData, entry_type: e.target.value as NutritionEntryCreate['entry_type'] })}
                      className="w-full px-3 py-2 bg-slate-900 border border-slate-700/50 rounded-lg text-white text-sm min-h-[44px]"
                    >
                      <option value="daily">Daily</option>
                      <option value="pre_activity">Pre-Run</option>
                      <option value="during_activity">During Run</option>
                      <option value="post_activity">Post-Run</option>
                    </select>
                  </div>
                  <div>
                    <label className="block text-xs font-medium mb-1 text-slate-400">Date</label>
                    <input
                      type="date"
                      value={formData.date}
                      onChange={(e) => setFormData({ ...formData, date: e.target.value })}
                      className="w-full px-3 py-2 bg-slate-900 border border-slate-700/50 rounded-lg text-white text-sm min-h-[44px]"
                    />
                  </div>
                </div>

                <div className="grid grid-cols-2 gap-3">
                  {[
                    { label: 'Calories', key: 'calories' as const },
                    { label: 'Protein (g)', key: 'protein_g' as const },
                    { label: 'Carbs (g)', key: 'carbs_g' as const },
                    { label: 'Fat (g)', key: 'fat_g' as const },
                  ].map(({ label, key }) => (
                    <div key={key}>
                      <label className="block text-xs font-medium mb-1 text-slate-400">{label}</label>
                      <input
                        type="number"
                        step="0.1"
                        value={formData[key] ?? ''}
                        onChange={(e) => setFormData({ ...formData, [key]: e.target.value ? parseFloat(e.target.value) : undefined })}
                        className="w-full px-3 py-2 bg-slate-900 border border-slate-700/50 rounded-lg text-white text-sm min-h-[44px]"
                        placeholder="—"
                      />
                    </div>
                  ))}
                </div>

                <div>
                  <label className="block text-xs font-medium mb-1 text-slate-400">Notes</label>
                  <input
                    value={formData.notes || ''}
                    onChange={(e) => setFormData({ ...formData, notes: e.target.value })}
                    className="w-full px-3 py-2 bg-slate-900 border border-slate-700/50 rounded-lg text-white text-sm min-h-[44px]"
                    placeholder="e.g., Pre-run oatmeal"
                  />
                </div>

                <div className="flex gap-2">
                  <button
                    type="submit"
                    disabled={createEntry.isPending}
                    className="flex-1 py-3 bg-blue-600 hover:bg-blue-700 disabled:bg-slate-700 rounded-lg text-white font-medium text-sm min-h-[44px]"
                  >
                    {createEntry.isPending ? <LoadingSpinner size="sm" /> : 'Log Entry'}
                  </button>
                  <button
                    type="button"
                    onClick={() => {
                      setShowForm(false);
                      setNlText('');
                      setFormData({
                        athlete_id: user?.id || '',
                        date: entryDate,
                        entry_type: 'daily',
                        calories: undefined,
                        protein_g: undefined,
                        carbs_g: undefined,
                        fat_g: undefined,
                        fiber_g: undefined,
                        notes: '',
                      });
                    }}
                    className="px-4 py-3 bg-slate-700 hover:bg-slate-600 rounded-lg text-slate-300 text-sm min-h-[44px]"
                  >
                    Cancel
                  </button>
                </div>
              </form>
            </div>
          )}

          {/* Live barcode scanner overlay */}
          {scannerOpen && (
            <>
              <div className="fixed inset-0 bg-black/70 z-40" onClick={stopScanner} />
              <div className="fixed bottom-0 left-0 right-0 z-50 bg-slate-800 rounded-t-2xl border-t border-slate-700/50 max-h-[75vh] overflow-hidden animate-slide-up">
                <div className="w-10 h-1 bg-slate-600 rounded-full mx-auto mt-3" />
                <div className="p-4 space-y-3">
                  <div className="flex items-center justify-between">
                    <h2 className="text-sm font-semibold text-white">Scan Barcode</h2>
                    <button onClick={stopScanner} className="text-slate-400 text-xs">Cancel</button>
                  </div>
                  {scannerLoading && (
                    <div className="flex items-center justify-center py-6">
                      <LoadingSpinner />
                      <span className="ml-2 text-xs text-slate-400">Starting camera...</span>
                    </div>
                  )}
                  <div id="barcode-live-reader" className="rounded-lg overflow-hidden" />
                  <p className="text-xs text-slate-500 text-center">Point camera at the barcode — it will scan automatically</p>
                </div>
              </div>
            </>
          )}

          {/* Goal Setup Bottom Sheet */}
          {showGoalSetup && (
            <>
              <div className="fixed inset-0 bg-black/70 z-40" onClick={() => setShowGoalSetup(false)} />
              <div className="fixed bottom-0 left-0 right-0 z-50 bg-slate-800 rounded-t-2xl border-t border-slate-700/50 max-h-[85vh] overflow-y-auto animate-slide-up">
                <div className="w-10 h-1 bg-slate-600 rounded-full mx-auto mt-3" />
                <div className="p-5 space-y-5">
                  <div className="flex items-center justify-between">
                    <h2 className="text-base font-semibold text-white">Nutrition Goal</h2>
                    <button onClick={() => setShowGoalSetup(false)} className="text-slate-400 text-xs min-h-[44px] flex items-center">Cancel</button>
                  </div>

                  {/* Goal Type */}
                  <div>
                    <label className="block text-xs text-slate-400 mb-2">What are you working toward?</label>
                    <div className="grid grid-cols-3 gap-2">
                      {([
                        ['performance', 'Performance', 'Fuel training fully'],
                        ['maintain', 'Maintain', 'Sustain current weight'],
                        ['recomp', 'Recomp', 'Lean out on rest days'],
                      ] as const).map(([value, title, desc]) => (
                        <button
                          key={value}
                          onClick={() => setGoalForm((f) => ({ ...f, goal_type: value }))}
                          className={`p-3 rounded-xl border text-left min-h-[72px] ${
                            goalForm.goal_type === value
                              ? 'border-blue-500 bg-blue-600/10'
                              : 'border-slate-600/50 bg-slate-700/50'
                          }`}
                        >
                          <span className="block text-sm font-medium text-white">{title}</span>
                          <span className="block text-[10px] text-slate-400 mt-0.5">{desc}</span>
                        </button>
                      ))}
                    </div>
                  </div>

                  {/* Protein */}
                  <div>
                    <label className="block text-xs text-slate-400 mb-1">Protein (g/kg body weight)</label>
                    <div className="flex items-center gap-3">
                      <input
                        type="range"
                        min="1.2"
                        max="2.4"
                        step="0.1"
                        value={goalForm.protein_g_per_kg}
                        onChange={(e) => setGoalForm((f) => ({ ...f, protein_g_per_kg: parseFloat(e.target.value) }))}
                        className="flex-1 accent-blue-500"
                      />
                      <span className="text-sm font-medium text-white w-10 text-right">{goalForm.protein_g_per_kg.toFixed(1)}</span>
                    </div>
                  </div>

                  {/* Carb/Fat split — linked slider */}
                  <div>
                    <label className="block text-xs text-slate-400 mb-1">
                      Remaining calories: Carbs {Math.round(goalForm.carb_pct * 100)}% / Fat {Math.round(goalForm.fat_pct * 100)}%
                    </label>
                    <input
                      type="range"
                      min="0.30"
                      max="0.75"
                      step="0.05"
                      value={goalForm.carb_pct}
                      onChange={(e) => {
                        const carb = parseFloat(e.target.value);
                        setGoalForm((f) => ({ ...f, carb_pct: carb, fat_pct: parseFloat((1 - carb).toFixed(2)) }));
                      }}
                      className="w-full accent-emerald-500"
                    />
                    <div className="flex justify-between text-[10px] text-slate-500 mt-1">
                      <span>More fat</span>
                      <span>More carbs</span>
                    </div>
                  </div>

                  {/* Caffeine */}
                  <div>
                    <label className="block text-xs text-slate-400 mb-1">Daily caffeine target (mg, optional)</label>
                    <input
                      type="number"
                      placeholder="e.g. 400"
                      value={goalForm.caffeine_target_mg ?? ''}
                      onChange={(e) => setGoalForm((f) => ({ ...f, caffeine_target_mg: e.target.value ? parseInt(e.target.value) : undefined }))}
                      className="w-full bg-slate-700 border border-slate-600/50 rounded-lg px-3 py-2.5 text-sm text-white placeholder-slate-500 min-h-[44px]"
                    />
                  </div>

                  {/* Load adaptive toggle */}
                  <div className="flex items-center justify-between">
                    <div>
                      <span className="text-sm text-white">Adapt to training load</span>
                      <p className="text-[10px] text-slate-500">Scale calories by workout intensity</p>
                    </div>
                    <button
                      onClick={() => setGoalForm((f) => ({ ...f, load_adaptive: !f.load_adaptive }))}
                      className={`w-11 h-6 rounded-full transition-colors flex items-center ${
                        goalForm.load_adaptive ? 'bg-blue-600 justify-end' : 'bg-slate-600 justify-start'
                      }`}
                    >
                      <div className="w-5 h-5 bg-white rounded-full mx-0.5 shadow" />
                    </button>
                  </div>

                  {/* Save */}
                  <button
                    onClick={handleSaveGoal}
                    disabled={upsertGoal.isPending}
                    className="w-full bg-blue-600 hover:bg-blue-700 text-white font-medium py-3 rounded-xl text-sm min-h-[48px] disabled:opacity-50 transition-colors"
                  >
                    {upsertGoal.isPending ? 'Saving...' : 'Save Goal'}
                  </button>
                </div>
              </div>
            </>
          )}

          {/* Catalog Browser Modal */}
          {showCatalog && (
            <>
              <div className="fixed inset-0 bg-black/50 z-40" onClick={() => setShowCatalog(false)} />
              <div className="fixed bottom-0 left-0 right-0 z-50 bg-slate-800 rounded-t-2xl border-t border-slate-700/50 max-h-[85vh] flex flex-col animate-slide-up">
                <div className="w-10 h-1 bg-slate-600 rounded-full mx-auto mt-3" />
                <div className="p-4 space-y-3 flex-shrink-0">
                  <div className="flex items-center justify-between">
                    <h2 className="text-sm font-semibold text-white">Fueling Products</h2>
                    <button
                      onClick={() => setShowCatalog(false)}
                      className="text-slate-400 hover:text-white min-w-[44px] min-h-[44px] flex items-center justify-center"
                    >
                      <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                        <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
                      </svg>
                    </button>
                  </div>

                  <input
                    value={catalogSearch}
                    onChange={(e) => setCatalogSearch(e.target.value)}
                    className="w-full px-3 py-2 bg-slate-900 border border-slate-700/50 rounded-lg text-white text-sm min-h-[44px]"
                    placeholder="Search brands or products..."
                  />

                  <div className="flex gap-2 overflow-x-auto pb-1 scrollbar-none">
                    {['', 'gel', 'drink_mix', 'chew', 'bar', 'electrolyte'].map((cat) => (
                      <button
                        key={cat}
                        onClick={() => setCatalogCategory(cat)}
                        className={`flex-shrink-0 px-3 py-1.5 rounded-full text-xs font-medium transition-colors ${
                          catalogCategory === cat
                            ? 'bg-blue-600 text-white'
                            : 'bg-slate-700 text-slate-300 hover:bg-slate-600'
                        }`}
                      >
                        {cat ? cat.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase()) : 'All'}
                      </button>
                    ))}
                  </div>
                </div>

                <div className="flex-1 overflow-y-auto px-4 pb-4 space-y-1.5">
                  {filteredCatalog.map((product) => {
                    const onShelf = shelfProductIds.has(product.id);
                    return (
                      <div key={product.id} className="flex items-center justify-between bg-slate-700/30 rounded-lg p-3">
                        <div className="flex-1 min-w-0">
                          <p className="text-sm font-medium text-white truncate">
                            {product.brand} {product.product_name}
                            {product.variant && <span className="text-slate-400"> — {product.variant}</span>}
                          </p>
                          <p className="text-xs text-slate-400">
                            {product.carbs_g}g C &middot; {product.calories} cal
                            {product.caffeine_mg ? ` · ${product.caffeine_mg}mg caf` : ''}
                          </p>
                        </div>
                        <button
                          onClick={async () => {
                            if (onShelf) {
                              await removeFromProfile.mutateAsync(product.id);
                              showToast(`Removed ${product.brand} ${product.product_name}`);
                            } else {
                              await addToProfile.mutateAsync({ productId: product.id });
                              showToast(`Added ${product.brand} ${product.product_name}`);
                            }
                          }}
                          className={`ml-2 min-w-[44px] min-h-[44px] flex items-center justify-center rounded-lg text-sm font-medium transition-colors ${
                            onShelf
                              ? 'bg-red-900/40 text-red-400 hover:bg-red-900/60'
                              : 'bg-blue-600/20 text-blue-400 hover:bg-blue-600/40'
                          }`}
                        >
                          {onShelf ? '−' : '+'}
                        </button>
                      </div>
                    );
                  })}
                  {filteredCatalog.length === 0 && (
                    <p className="text-sm text-slate-500 text-center py-8">No products match your search.</p>
                  )}
                </div>
              </div>
            </>
          )}

          {/* Photo preview (behind bottom sheet) */}
          {photoPreview && !photoItems && (
            <div className="relative rounded-xl overflow-hidden">
              <img src={photoPreview} alt="Meal" className="w-full max-h-64 object-cover" />
              {parsePhoto.isPending && (
                <div className="absolute inset-0 bg-slate-900/60 flex items-center justify-center">
                  <div className="flex flex-col items-center gap-3">
                    <LoadingSpinner size="sm" />
                    <span className="text-sm text-white">Analyzing your meal...</span>
                  </div>
                </div>
              )}
            </div>
          )}

          {/* Photo Confirmation Bottom Sheet */}
          {photoPreview && photoItems && (
            <>
              <div
                className="fixed inset-0 bg-black/50 z-40"
                onClick={() => { setPhotoPreview(null); setPhotoItems(null); }}
              />
              <div className="fixed bottom-0 left-0 right-0 z-50 bg-slate-800 rounded-t-2xl border-t border-slate-700/50 max-h-[85vh] overflow-y-auto animate-slide-up">
                <div className="w-10 h-1 bg-slate-600 rounded-full mx-auto mt-3" />
                <div className="p-4 space-y-3">
                  <div className="flex items-center justify-between">
                    <h2 className="text-sm font-semibold text-white">Detected Items</h2>
                    <img src={photoPreview} alt="Meal" className="w-12 h-12 rounded-lg object-cover" />
                  </div>

                  {templateMatch && (
                    <button
                      onClick={() => {
                        const tmplItems = templateMatch.items as Array<{ food?: string; calories?: number; protein_g?: number; carbs_g?: number; fat_g?: number; fiber_g?: number; grams?: number; macro_source?: string }>;
                        setPhotoItems(tmplItems.map((ti) => ({
                          food: ti.food || '',
                          grams: ti.grams || 0,
                          calories: ti.calories || 0,
                          protein_g: ti.protein_g || 0,
                          carbs_g: ti.carbs_g || 0,
                          fat_g: ti.fat_g || 0,
                          fiber_g: ti.fiber_g || 0,
                          macro_source: ti.macro_source || 'template',
                        })));
                        setTemplateMatch(null);
                      }}
                      className="w-full bg-emerald-900/30 border border-emerald-700/40 rounded-lg p-3 text-left active:bg-emerald-900/50 transition-colors"
                    >
                      <p className="text-xs font-medium text-emerald-400">Your usual meal?</p>
                      <p className="text-xs text-slate-400 mt-0.5">
                        Logged {templateMatch.times_confirmed} times — tap to use saved portions
                      </p>
                    </button>
                  )}

                  {photoItems.map((item, idx) => (
                    <div key={idx} className="bg-slate-700/40 rounded-lg p-3 space-y-2">
                      <div className="flex items-center justify-between">
                        <p className="text-sm font-medium text-white truncate flex-1 min-w-0">{item.food}</p>
                        <button
                          onClick={() => removePhotoItem(idx)}
                          className="ml-2 text-slate-500 hover:text-red-400 min-w-[44px] min-h-[44px] flex items-center justify-center"
                        >
                          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                            <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
                          </svg>
                        </button>
                      </div>
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-2">
                          <button
                            onClick={() => adjustPortion(idx, -10)}
                            className="w-9 h-9 bg-slate-600 rounded-lg text-sm flex items-center justify-center active:bg-slate-500"
                          >
                            -
                          </button>
                          <span className="text-sm font-medium text-white w-14 text-center">{Math.round(item.grams)}g</span>
                          <button
                            onClick={() => adjustPortion(idx, 10)}
                            className="w-9 h-9 bg-slate-600 rounded-lg text-sm flex items-center justify-center active:bg-slate-500"
                          >
                            +
                          </button>
                        </div>
                        <p className="text-xs text-slate-400">
                          {Math.round(item.calories)} cal &middot; {Math.round(item.protein_g)}P {Math.round(item.carbs_g)}C {Math.round(item.fat_g)}F
                        </p>
                      </div>
                    </div>
                  ))}

                  <div className="border-t border-slate-700 pt-3 text-sm text-slate-300">
                    Total: {Math.round(photoItems.reduce((s, i) => s + i.calories, 0))} cal
                    &middot; {Math.round(photoItems.reduce((s, i) => s + i.protein_g, 0))}g P
                    &middot; {Math.round(photoItems.reduce((s, i) => s + i.carbs_g, 0))}g C
                    &middot; {Math.round(photoItems.reduce((s, i) => s + i.fat_g, 0))}g F
                  </div>

                  <div className="flex gap-2 pb-safe">
                    <button
                      onClick={handleConfirmPhoto}
                      disabled={createEntry.isPending}
                      className="flex-1 py-3 bg-blue-600 hover:bg-blue-700 disabled:bg-slate-700 rounded-lg text-white font-medium text-sm min-h-[44px]"
                    >
                      {createEntry.isPending ? <LoadingSpinner size="sm" /> : 'Looks right'}
                    </button>
                    <button
                      onClick={() => { setPhotoPreview(null); setPhotoItems(null); }}
                      className="px-4 py-3 bg-slate-700 hover:bg-slate-600 rounded-lg text-slate-300 text-sm min-h-[44px]"
                    >
                      Cancel
                    </button>
                  </div>
                </div>
              </div>
            </>
          )}

          {/* Barcode Result */}
          {barcodeResult && (
            <div className="bg-slate-800 rounded-xl border border-slate-700/50 p-4 space-y-3">
              <div className="flex items-center gap-2 flex-wrap">
                <h2 className="text-sm font-semibold">{barcodeResult.food_name}</h2>
                {barcodeResult.is_athlete_override && (
                  <span
                    className="text-[10px] uppercase tracking-wide font-medium px-2 py-0.5 rounded bg-emerald-900/40 text-emerald-300 border border-emerald-700/40"
                    title="Showing your saved correction for this food"
                  >
                    Your values
                  </span>
                )}
              </div>
              <p className="text-xs text-slate-400">
                Per serving: {barcodeResult.calories} cal &middot; {barcodeResult.protein_g}g P &middot; {barcodeResult.carbs_g}g C &middot; {barcodeResult.fat_g}g F
              </p>
              <div className="flex items-center gap-4">
                <span className="text-sm text-slate-300">Servings:</span>
                <div className="flex items-center gap-2">
                  <button
                    onClick={() => setBarcodeResult({ ...barcodeResult, servings: Math.max(0.5, barcodeResult.servings - 0.5) })}
                    className="w-11 h-11 bg-slate-700 rounded-lg text-lg flex items-center justify-center active:bg-slate-600"
                  >
                    -
                  </button>
                  <span className="w-8 text-center font-medium">{barcodeResult.servings}</span>
                  <button
                    onClick={() => setBarcodeResult({ ...barcodeResult, servings: barcodeResult.servings + 0.5 })}
                    className="w-11 h-11 bg-slate-700 rounded-lg text-lg flex items-center justify-center active:bg-slate-600"
                  >
                    +
                  </button>
                </div>
              </div>
              <div className="flex gap-2">
                <button
                  onClick={handleConfirmBarcode}
                  disabled={createEntry.isPending}
                  className="flex-1 py-3 bg-blue-600 hover:bg-blue-700 disabled:bg-slate-700 rounded-lg text-white font-medium text-sm min-h-[44px]"
                >
                  Log
                </button>
                <button
                  onClick={() => setBarcodeResult(null)}
                  className="px-4 py-3 bg-slate-700 hover:bg-slate-600 rounded-lg text-slate-300 text-sm min-h-[44px]"
                >
                  Cancel
                </button>
              </div>
            </div>
          )}

          {/* ======================== TAB 1: LOG ======================== */}
          {activeTab === 'log' && (
            <>
              {/* Daily Target Progress or Summary */}
              {dailyTarget ? (
                <div className="bg-slate-800 rounded-xl border border-slate-700/50 p-4 space-y-3">
                  <div className="flex items-center justify-between">
                    <div>
                      <h1 className="text-lg font-semibold">Today&apos;s Nutrition</h1>
                      <p className="text-xs text-slate-400 mt-0.5">
                        {dailyTarget.day_tier_label}
                        {dailyTarget.workout_title ? ` — ${dailyTarget.workout_title}` : ''}
                        {' '}({dailyTarget.multiplier}x)
                      </p>
                    </div>
                    <button
                      onClick={() => setShowGoalSetup(true)}
                      className="text-xs text-slate-500 hover:text-slate-300 min-h-[44px] flex items-center px-2"
                    >
                      Edit
                    </button>
                  </div>

                  {/* Calorie progress */}
                  {(() => {
                    const pct = Math.min(100, (dailyTarget.actual_calories / dailyTarget.calorie_target) * 100);
                    const overUnder = dailyTarget.actual_calories - dailyTarget.calorie_target;
                    const barColor = pct > 110 ? 'bg-amber-500' : pct > 90 ? 'bg-green-500' : 'bg-blue-500';
                    return (
                      <div>
                        <div className="flex justify-between text-sm mb-1">
                          <span className="text-white font-medium">{Math.round(dailyTarget.actual_calories)} / {dailyTarget.calorie_target} cal</span>
                          <span className={`text-xs ${overUnder > 0 ? 'text-amber-400' : 'text-slate-400'}`}>
                            {overUnder > 0 ? '+' : ''}{Math.round(overUnder)}
                          </span>
                        </div>
                        <div className="w-full bg-slate-700 rounded-full h-2">
                          <div className={`${barColor} h-2 rounded-full transition-all`} style={{ width: `${Math.min(pct, 100)}%` }} />
                        </div>
                        <div className="flex justify-between mt-1">
                          <span className="text-[10px] text-slate-500">{Math.round(dailyTarget.time_pct)}% of day</span>
                          <span className="text-[10px] text-slate-500">{Math.round(pct)}% of target</span>
                        </div>
                      </div>
                    );
                  })()}

                  {/* Macro bars */}
                  <div className="grid grid-cols-3 gap-3 text-xs">
                    {([
                      ['P', dailyTarget.actual_protein_g, dailyTarget.protein_g, 'bg-blue-500'],
                      ['C', dailyTarget.actual_carbs_g, dailyTarget.carbs_g, 'bg-emerald-500'],
                      ['F', dailyTarget.actual_fat_g, dailyTarget.fat_g, 'bg-amber-500'],
                    ] as const).map(([label, actual, target, color]) => {
                      const mpct = target > 0 ? Math.min(100, (actual / target) * 100) : 0;
                      return (
                        <div key={label}>
                          <div className="flex justify-between mb-0.5">
                            <span className="text-slate-400">{label}</span>
                            <span className="text-slate-300">{Math.round(actual)}/{Math.round(target)}g</span>
                          </div>
                          <div className="w-full bg-slate-700 rounded-full h-1.5">
                            <div className={`${color} h-1.5 rounded-full transition-all`} style={{ width: `${mpct}%` }} />
                          </div>
                        </div>
                      );
                    })}
                  </div>

                  {dailyTarget.caffeine_mg != null && dailyTarget.caffeine_mg > 0 && (
                    <div className="text-xs text-slate-400">
                      Caffeine: {Math.round(dailyTarget.actual_caffeine_mg)} / {dailyTarget.caffeine_mg}mg
                    </div>
                  )}

                  {dailyTarget.insights.length > 0 && (
                    <div className="bg-slate-700/50 rounded-lg p-2.5 border border-slate-600/30">
                      <p className="text-xs text-blue-300">{dailyTarget.insights[0].text}</p>
                    </div>
                  )}
                </div>
              ) : (
                <div className="bg-slate-800 rounded-xl border border-slate-700/50 p-4">
                  <div className="flex items-center justify-between">
                    <div>
                      <h1 className="text-lg font-semibold">Today&apos;s Nutrition</h1>
                      {entries && entries.length > 0 ? (
                        <div className="flex flex-wrap gap-x-4 gap-y-1 text-sm text-slate-300 mt-1">
                          <span className="font-medium text-white">{Math.round(totals.cal)} cal</span>
                          <span>{Math.round(totals.protein)}g P</span>
                          <span>{Math.round(totals.carbs)}g C</span>
                          <span>{Math.round(totals.fat)}g F</span>
                          {totals.caffeine > 0 && <span>{Math.round(totals.caffeine)}mg caf</span>}
                        </div>
                      ) : (
                        <p className="text-sm text-slate-500 mt-1">No entries today. Log when convenient.</p>
                      )}
                    </div>
                    <button
                      onClick={() => setShowGoalSetup(true)}
                      className="text-xs text-blue-400 hover:text-blue-300 min-h-[44px] flex items-center px-2"
                    >
                      Set goals
                    </button>
                  </div>
                </div>
              )}

              {/* Input Modes */}
              {!showForm && !photoPreview && !barcodeResult && !scannerOpen && (
                <>
                  <div className="grid grid-cols-3 gap-3">
                    <button
                      onClick={() => photoRef.current?.click()}
                      className="flex flex-col items-center justify-center gap-2 bg-slate-800 rounded-xl border border-slate-700/50 p-4 min-h-[88px] active:bg-slate-700 transition-colors"
                    >
                      <svg className="w-7 h-7 text-blue-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                        <path strokeLinecap="round" strokeLinejoin="round" d="M6.827 6.175A2.31 2.31 0 015.186 7.23c-.38.054-.757.112-1.134.175C2.999 7.58 2.25 8.507 2.25 9.574V18a2.25 2.25 0 002.25 2.25h15A2.25 2.25 0 0021.75 18V9.574c0-1.067-.75-1.994-1.802-2.169a47.865 47.865 0 00-1.134-.175 2.31 2.31 0 01-1.64-1.055l-.822-1.316a2.192 2.192 0 00-1.736-1.039 48.774 48.774 0 00-5.232 0 2.192 2.192 0 00-1.736 1.039l-.821 1.316z" />
                        <path strokeLinecap="round" strokeLinejoin="round" d="M16.5 12.75a4.5 4.5 0 11-9 0 4.5 4.5 0 019 0z" />
                      </svg>
                      <span className="text-xs text-slate-400">Photo</span>
                    </button>
                    <button
                      onClick={startScanner}
                      className="flex flex-col items-center justify-center gap-2 bg-slate-800 rounded-xl border border-slate-700/50 p-4 min-h-[88px] active:bg-slate-700 transition-colors"
                    >
                      <svg className="w-7 h-7 text-purple-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                        <path strokeLinecap="round" strokeLinejoin="round" d="M3.75 4.875c0-.621.504-1.125 1.125-1.125h4.5c.621 0 1.125.504 1.125 1.125v4.5c0 .621-.504 1.125-1.125 1.125h-4.5A1.125 1.125 0 013.75 9.375v-4.5zM3.75 14.625c0-.621.504-1.125 1.125-1.125h4.5c.621 0 1.125.504 1.125 1.125v4.5c0 .621-.504 1.125-1.125 1.125h-4.5a1.125 1.125 0 01-1.125-1.125v-4.5zM13.5 4.875c0-.621.504-1.125 1.125-1.125h4.5c.621 0 1.125.504 1.125 1.125v4.5c0 .621-.504 1.125-1.125 1.125h-4.5A1.125 1.125 0 0113.5 9.375v-4.5z" />
                        <path strokeLinecap="round" strokeLinejoin="round" d="M6.75 6.75h.75v.75h-.75v-.75zM6.75 16.5h.75v.75h-.75v-.75zM16.5 6.75h.75v.75h-.75v-.75zM13.5 13.5h.75v.75h-.75v-.75zM13.5 19.5h.75v.75h-.75v-.75zM19.5 13.5h.75v.75h-.75v-.75zM19.5 19.5h.75v.75h-.75v-.75zM16.5 16.5h.75v.75h-.75v-.75z" />
                      </svg>
                      <span className="text-xs text-slate-400">Scan</span>
                    </button>
                    <button
                      onClick={() => {
                        setFormData((prev) => ({ ...prev, date: entryDate }));
                        setShowForm(true);
                      }}
                      className="flex flex-col items-center justify-center gap-2 bg-slate-800 rounded-xl border border-slate-700/50 p-4 min-h-[88px] active:bg-slate-700 transition-colors"
                    >
                      <svg className="w-7 h-7 text-emerald-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                        <path strokeLinecap="round" strokeLinejoin="round" d="M16.862 4.487l1.687-1.688a1.875 1.875 0 112.652 2.652L10.582 16.07a4.5 4.5 0 01-1.897 1.13L6 18l.8-2.685a4.5 4.5 0 011.13-1.897l8.932-8.931zm0 0L19.5 7.125M18 14v4.75A2.25 2.25 0 0115.75 21H5.25A2.25 2.25 0 013 18.75V8.25A2.25 2.25 0 015.25 6H10" />
                      </svg>
                      <span className="text-xs text-slate-400">Type it</span>
                    </button>
                  </div>
                </>
              )}

              {/* Fueling Shelf */}
              {!showForm && !photoPreview && !barcodeResult && !scannerOpen && (
                <div className="bg-slate-800 rounded-xl border border-slate-700/50 p-4">
                  <div className="flex items-center justify-between mb-3">
                    <h2 className="text-sm font-semibold text-slate-300">My Fueling Shelf</h2>
                    <button
                      onClick={() => setShowCatalog(true)}
                      className="text-xs text-blue-400 hover:text-blue-300 min-h-[44px] flex items-center px-2"
                    >
                      + Add products
                    </button>
                  </div>
                  {shelfItems && shelfItems.length > 0 ? (
                    <div className="flex gap-2 overflow-x-auto pb-2 -mx-1 px-1 scrollbar-none">
                      {shelfItems.map((item) => (
                        <button
                          key={item.id}
                          onClick={() => handleShelfTap(item.product.id, `${item.product.brand} ${item.product.product_name}`)}
                          className="flex-shrink-0 flex flex-col items-start bg-slate-700/60 rounded-lg border border-slate-600/50 px-3 py-2 min-w-[100px] max-w-[130px] min-h-[56px] active:bg-slate-600 transition-colors"
                        >
                          <span className="text-[10px] text-slate-500 leading-tight">{item.product.brand}</span>
                          <span className="text-xs font-medium text-white leading-tight line-clamp-2">
                            {item.product.product_name}{item.product.variant ? ` ${item.product.variant}` : ''}
                          </span>
                          <span className="text-[10px] text-slate-400 mt-0.5">
                            {item.product.calories ? `${item.product.calories} cal` : ''}
                            {item.product.caffeine_mg ? ` · ${item.product.caffeine_mg}mg caf` : ''}
                          </span>
                        </button>
                      ))}
                    </div>
                  ) : (
                    <p className="text-xs text-slate-500">Tap &quot;+ Add products&quot; to build your fueling shelf for one-tap logging.</p>
                  )}
                </div>
              )}

              {/* Today's Log */}
              {entries && entries.length > 0 && (
                <div className="space-y-2">
                  <h2 className="text-sm font-semibold text-slate-400 px-1">Today&apos;s Log</h2>
                  {entries.map((entry) => (
                    <div key={entry.id} className="bg-slate-800 rounded-xl border border-slate-700/50 p-3">
                      {editingEntryId === entry.id ? (
                        <div className="space-y-3">
                          <div>
                            <label className="block text-xs text-slate-500 mb-1">Notes</label>
                            <input
                              value={editForm.notes ?? ''}
                              onChange={(e) => setEditForm({ ...editForm, notes: e.target.value })}
                              className="w-full px-3 py-2 bg-slate-900 border border-slate-700/50 rounded-lg text-white text-sm min-h-[44px]"
                            />
                          </div>
                          <div className="grid grid-cols-4 gap-2">
                            <div>
                              <label className="block text-[10px] text-slate-500 mb-0.5">Cal</label>
                              <input
                                type="number"
                                value={editForm.calories ?? ''}
                                onChange={(e) => setEditForm({ ...editForm, calories: e.target.value ? Number(e.target.value) : undefined })}
                                className="w-full px-2 py-1.5 bg-slate-900 border border-slate-700/50 rounded text-white text-sm"
                              />
                            </div>
                            <div>
                              <label className="block text-[10px] text-slate-500 mb-0.5">Protein</label>
                              <input
                                type="number"
                                value={editForm.protein_g ?? ''}
                                onChange={(e) => setEditForm({ ...editForm, protein_g: e.target.value ? Number(e.target.value) : undefined })}
                                className="w-full px-2 py-1.5 bg-slate-900 border border-slate-700/50 rounded text-white text-sm"
                              />
                            </div>
                            <div>
                              <label className="block text-[10px] text-slate-500 mb-0.5">Carbs</label>
                              <input
                                type="number"
                                value={editForm.carbs_g ?? ''}
                                onChange={(e) => setEditForm({ ...editForm, carbs_g: e.target.value ? Number(e.target.value) : undefined })}
                                className="w-full px-2 py-1.5 bg-slate-900 border border-slate-700/50 rounded text-white text-sm"
                              />
                            </div>
                            <div>
                              <label className="block text-[10px] text-slate-500 mb-0.5">Fat</label>
                              <input
                                type="number"
                                value={editForm.fat_g ?? ''}
                                onChange={(e) => setEditForm({ ...editForm, fat_g: e.target.value ? Number(e.target.value) : undefined })}
                                className="w-full px-2 py-1.5 bg-slate-900 border border-slate-700/50 rounded text-white text-sm"
                              />
                            </div>
                          </div>
                          <div className="flex gap-2 justify-end">
                            <button
                              onClick={() => handleDeleteEntry(entry.id)}
                              disabled={deleteEntry.isPending}
                              className="px-3 py-1.5 text-red-400 text-xs hover:bg-red-400/10 rounded min-h-[36px]"
                            >
                              Delete
                            </button>
                            <button
                              onClick={() => setEditingEntryId(null)}
                              className="px-3 py-1.5 text-slate-400 text-xs hover:bg-slate-700 rounded min-h-[36px]"
                            >
                              Cancel
                            </button>
                            <button
                              onClick={handleSaveEdit}
                              disabled={updateEntry.isPending}
                              className="px-3 py-1.5 bg-blue-600 hover:bg-blue-500 text-white text-xs rounded min-h-[36px]"
                            >
                              {updateEntry.isPending ? 'Saving...' : 'Save'}
                            </button>
                          </div>
                        </div>
                      ) : (
                        <button
                          onClick={() => startEditing(entry)}
                          className="w-full text-left"
                        >
                          <div className="flex justify-between items-start">
                            <div className="min-w-0 flex-1">
                              {entry.notes && <p className="text-sm text-white truncate">{entry.notes}</p>}
                              <div className="flex items-center gap-2 text-xs text-slate-400 mt-0.5">
                                <span className="capitalize">{entry.entry_type.replace(/_/g, ' ')}</span>
                                {macroSourceBadge(entry.macro_source)}
                              </div>
                            </div>
                            <div className="flex items-center gap-2 flex-shrink-0 ml-2">
                              <div className="text-right text-xs text-slate-300">
                                {entry.calories != null && <div>{Math.round(entry.calories)} cal</div>}
                                <div className="text-slate-500">
                                  {entry.protein_g != null && `${Math.round(entry.protein_g)}P `}
                                  {entry.carbs_g != null && `${Math.round(entry.carbs_g)}C `}
                                  {entry.fat_g != null && `${Math.round(entry.fat_g)}F`}
                                </div>
                              </div>
                              <svg className="w-3.5 h-3.5 text-slate-600" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                                <path strokeLinecap="round" strokeLinejoin="round" d="M16.862 4.487l1.687-1.688a1.875 1.875 0 112.652 2.652L10.582 16.07a4.5 4.5 0 01-1.897 1.13L6 18l.8-2.685a4.5 4.5 0 011.13-1.897l8.932-8.931z" />
                              </svg>
                            </div>
                          </div>
                        </button>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </>
          )}

          {/* ======================== TAB: MEALS (Saved meals) ======================== */}
          {activeTab === 'meals' && (
            <>
              <div className="bg-slate-800 rounded-xl border border-slate-700/50 p-4">
                <div className="flex items-center justify-between mb-3">
                  <h2 className="text-sm font-semibold">Saved meals</h2>
                  <button
                    onClick={() => {
                      setEditingMealId(null);
                      setMealForm({
                        name: '',
                        items: [{ food: '', calories: undefined, protein_g: undefined, carbs_g: undefined, fat_g: undefined }],
                      });
                      setShowMealForm(true);
                    }}
                    className="text-xs px-3 py-1.5 rounded-lg bg-blue-600 text-white hover:bg-blue-700 active:bg-blue-800 min-h-[36px]"
                  >
                    + New meal
                  </button>
                </div>
                <p className="text-xs text-slate-400 mb-3">
                  Save meals you log often (like &ldquo;Workday Breakfast&rdquo;) and re-log them in one tap.
                </p>

                {showMealForm && (
                  <div className="mb-4 p-3 bg-slate-900 rounded-lg border border-slate-700/50 space-y-2">
                    <input
                      type="text"
                      placeholder="Meal name (e.g. Workday Breakfast)"
                      value={mealForm.name}
                      onChange={(e) => setMealForm({ ...mealForm, name: e.target.value })}
                      className="w-full px-3 py-2 bg-slate-800 rounded text-sm"
                    />

                    {nlAvailable?.available && (
                      <div className="space-y-1.5">
                        <label className="block text-xs text-slate-400">
                          Paste your meal and we&rsquo;ll fill in the macros
                        </label>
                        <div className="flex gap-2">
                          <textarea
                            value={mealParseText}
                            onChange={(e) => setMealParseText(e.target.value)}
                            rows={2}
                            placeholder='"2 eggs scrambled, 1 slice whole wheat toast, 1 tbsp peanut butter"'
                            className="flex-1 px-2 py-1.5 bg-slate-800 rounded text-xs resize-y"
                          />
                          <button
                            type="button"
                            disabled={parseMealItems.isPending || !mealParseText.trim()}
                            onClick={async () => {
                              const text = mealParseText.trim();
                              if (!text) return;
                              try {
                                const result = await parseMealItems.mutateAsync(text);
                                if (!result.items.length) {
                                  showToast('Couldn\u2019t recognize any foods');
                                  return;
                                }
                                const parsedItems: MealTemplateItem[] = result.items.map((it) => ({
                                  food: it.food,
                                  calories: it.calories,
                                  protein_g: it.protein_g,
                                  carbs_g: it.carbs_g,
                                  fat_g: it.fat_g,
                                  fiber_g: it.fiber_g,
                                }));
                                // Replace the empty starter row, otherwise
                                // append. Either way every parsed item is
                                // editable in the rows below.
                                const existing = mealForm.items.filter((i) => i.food.trim());
                                setMealForm({
                                  ...mealForm,
                                  items: existing.length ? [...existing, ...parsedItems] : parsedItems,
                                });
                                setMealParseText('');
                                showToast(`Added ${parsedItems.length} item${parsedItems.length === 1 ? '' : 's'}`);
                              } catch {
                                showToast('Couldn\u2019t parse that meal');
                              }
                            }}
                            className="px-3 py-1.5 bg-slate-700 hover:bg-slate-600 disabled:bg-slate-800 disabled:cursor-not-allowed rounded text-xs text-slate-200 self-start"
                          >
                            {parseMealItems.isPending ? <LoadingSpinner size="sm" /> : 'Parse'}
                          </button>
                        </div>
                      </div>
                    )}

                    {mealForm.items.map((item, idx) => (
                      <div key={idx} className="grid grid-cols-12 gap-1.5 items-center">
                        <input
                          type="text"
                          placeholder="Food"
                          value={item.food}
                          onChange={(e) => {
                            const items = [...mealForm.items];
                            items[idx] = { ...items[idx], food: e.target.value };
                            setMealForm({ ...mealForm, items });
                          }}
                          className="col-span-5 px-2 py-1.5 bg-slate-800 rounded text-xs"
                        />
                        <input
                          type="number"
                          placeholder="cal"
                          value={item.calories ?? ''}
                          onChange={(e) => {
                            const items = [...mealForm.items];
                            items[idx] = { ...items[idx], calories: e.target.value ? Number(e.target.value) : undefined };
                            setMealForm({ ...mealForm, items });
                          }}
                          className="col-span-2 px-2 py-1.5 bg-slate-800 rounded text-xs"
                        />
                        <input
                          type="number"
                          placeholder="P"
                          value={item.protein_g ?? ''}
                          onChange={(e) => {
                            const items = [...mealForm.items];
                            items[idx] = { ...items[idx], protein_g: e.target.value ? Number(e.target.value) : undefined };
                            setMealForm({ ...mealForm, items });
                          }}
                          className="col-span-1 px-1.5 py-1.5 bg-slate-800 rounded text-xs"
                        />
                        <input
                          type="number"
                          placeholder="C"
                          value={item.carbs_g ?? ''}
                          onChange={(e) => {
                            const items = [...mealForm.items];
                            items[idx] = { ...items[idx], carbs_g: e.target.value ? Number(e.target.value) : undefined };
                            setMealForm({ ...mealForm, items });
                          }}
                          className="col-span-1 px-1.5 py-1.5 bg-slate-800 rounded text-xs"
                        />
                        <input
                          type="number"
                          placeholder="F"
                          value={item.fat_g ?? ''}
                          onChange={(e) => {
                            const items = [...mealForm.items];
                            items[idx] = { ...items[idx], fat_g: e.target.value ? Number(e.target.value) : undefined };
                            setMealForm({ ...mealForm, items });
                          }}
                          className="col-span-1 px-1.5 py-1.5 bg-slate-800 rounded text-xs"
                        />
                        <button
                          onClick={() => {
                            const items = mealForm.items.filter((_, i) => i !== idx);
                            setMealForm({ ...mealForm, items: items.length ? items : [{ food: '' }] });
                          }}
                          className="col-span-2 text-xs text-slate-400 hover:text-red-400"
                          aria-label="Remove item"
                        >
                          remove
                        </button>
                      </div>
                    ))}
                    <button
                      onClick={() => setMealForm({ ...mealForm, items: [...mealForm.items, { food: '' }] })}
                      className="text-xs text-blue-400 hover:text-blue-300"
                    >
                      + add another item
                    </button>
                    <div className="flex gap-2 pt-2">
                      <button
                        onClick={async () => {
                          const validItems = mealForm.items.filter((i) => i.food.trim());
                          if (!mealForm.name.trim() || !validItems.length) {
                            showToast('Name and at least one food required');
                            return;
                          }
                          try {
                            if (editingMealId) {
                              await updateMeal.mutateAsync({
                                id: editingMealId,
                                updates: { name: mealForm.name.trim(), items: validItems },
                              });
                              showToast('Meal updated');
                            } else {
                              await createMeal.mutateAsync({ name: mealForm.name.trim(), items: validItems });
                              showToast('Meal saved');
                            }
                            setShowMealForm(false);
                            setEditingMealId(null);
                          } catch {
                            showToast('Failed to save meal');
                          }
                        }}
                        className="flex-1 py-2 bg-blue-600 hover:bg-blue-700 rounded text-white text-sm"
                      >
                        {editingMealId ? 'Update' : 'Save meal'}
                      </button>
                      <button
                        onClick={() => {
                          setShowMealForm(false);
                          setEditingMealId(null);
                        }}
                        className="px-4 py-2 bg-slate-700 hover:bg-slate-600 rounded text-slate-300 text-sm"
                      >
                        Cancel
                      </button>
                    </div>
                  </div>
                )}

                {!meals && <p className="text-xs text-slate-500">Loading…</p>}
                {meals && meals.length === 0 && !showMealForm && (
                  <p className="text-xs text-slate-500 italic">No saved meals yet. Tap &ldquo;+ New meal&rdquo; above.</p>
                )}
                {meals && meals.length > 0 && (
                  <div className="space-y-2">
                    {meals.map((m: MealTemplate) => (
                      <div key={m.id} className="p-3 rounded-lg bg-slate-900 border border-slate-700/50">
                        <div className="flex items-start justify-between mb-1">
                          <div>
                            <div className="text-sm font-medium text-slate-100">{m.name || 'Unnamed meal'}</div>
                            <div className="text-[11px] text-slate-400">
                              {Math.round(m.total_calories)} cal · {Math.round(m.total_protein_g)}g P · {Math.round(m.total_carbs_g)}g C · {Math.round(m.total_fat_g)}g F
                              {m.items?.length ? ` · ${m.items.length} item${m.items.length === 1 ? '' : 's'}` : ''}
                            </div>
                          </div>
                          <div className="flex gap-1">
                            <button
                              onClick={async () => {
                                try {
                                  await logMeal.mutateAsync({
                                    id: m.id,
                                    body: { date: selectedDate, entry_type: 'daily' },
                                  });
                                  showToast(`Logged: ${m.name}`);
                                } catch {
                                  showToast('Failed to log');
                                }
                              }}
                              className="text-xs px-3 py-1.5 rounded bg-blue-600 text-white hover:bg-blue-700 min-h-[36px]"
                            >
                              Log
                            </button>
                            <button
                              onClick={() => {
                                setEditingMealId(m.id);
                                setMealForm({
                                  name: m.name || '',
                                  items: (m.items as MealTemplateItem[]) || [{ food: '' }],
                                });
                                setShowMealForm(true);
                              }}
                              className="text-xs px-2 py-1.5 rounded bg-slate-700 text-slate-300 hover:bg-slate-600 min-h-[36px]"
                            >
                              Edit
                            </button>
                            <button
                              onClick={async () => {
                                if (!confirm(`Delete "${m.name}"?`)) return;
                                try {
                                  await deleteMeal.mutateAsync(m.id);
                                  showToast('Deleted');
                                } catch {
                                  showToast('Failed to delete');
                                }
                              }}
                              className="text-xs px-2 py-1.5 rounded bg-slate-700 text-slate-400 hover:text-red-400 min-h-[36px]"
                              aria-label="Delete meal"
                            >
                              ×
                            </button>
                          </div>
                        </div>
                        {m.items && m.items.length > 0 && (
                          <div className="text-[11px] text-slate-500 truncate">
                            {m.items.map((i) => i.food).filter(Boolean).join(', ')}
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </>
          )}

          {/* ======================== TAB 2: HISTORY ======================== */}
          {activeTab === 'history' && (
            <>
              {/* Date Navigation */}
              <div className="flex items-center justify-between bg-slate-800 rounded-xl border border-slate-700/50 px-2 py-1">
                <button
                  onClick={() => setSelectedDate(shiftDate(selectedDate, -1))}
                  className="min-w-[44px] min-h-[44px] flex items-center justify-center text-slate-400 active:text-white"
                >
                  <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M15 19l-7-7 7-7" />
                  </svg>
                </button>
                <div className="flex items-center gap-2">
                  <span className="text-sm font-semibold text-white">{formatDateShort(selectedDate)}</span>
                  {selectedDate !== today && (
                    <button
                      onClick={() => setSelectedDate(today)}
                      className="text-[10px] font-medium text-blue-400 bg-blue-900/30 border border-blue-700/40 rounded px-1.5 py-0.5"
                    >
                      Today
                    </button>
                  )}
                </div>
                <button
                  onClick={() => {
                    if (selectedDate < today) setSelectedDate(shiftDate(selectedDate, 1));
                  }}
                  className={`min-w-[44px] min-h-[44px] flex items-center justify-center ${
                    selectedDate >= today ? 'text-slate-700' : 'text-slate-400 active:text-white'
                  }`}
                  disabled={selectedDate >= today}
                >
                  <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7" />
                  </svg>
                </button>
              </div>

              {/* Selected Date Totals */}
              <div className="bg-slate-800 rounded-xl border border-slate-700/50 p-4 space-y-2">
                <h2 className="text-sm font-semibold text-slate-300">{formatDateShort(selectedDate)} Totals</h2>
                {(() => {
                  const ht = selectedDate === today ? dailyTarget : historyTarget;
                  if (ht && historyEntries && historyEntries.length > 0) {
                    const calPct = ht.calorie_target > 0 ? Math.round((historyTotals.cal / ht.calorie_target) * 100) : 0;
                    return (
                      <>
                        <p className="text-xs text-slate-400">{ht.day_tier_label} ({ht.multiplier}x)</p>
                        <div className="flex justify-between text-sm">
                          <span className="text-white font-medium">{Math.round(historyTotals.cal)} / {ht.calorie_target} cal</span>
                          <span className="text-xs text-slate-400">{calPct}%</span>
                        </div>
                        <div className="w-full bg-slate-700 rounded-full h-1.5">
                          <div className={`h-1.5 rounded-full ${calPct > 110 ? 'bg-amber-500' : calPct > 90 ? 'bg-green-500' : 'bg-blue-500'}`} style={{ width: `${Math.min(calPct, 100)}%` }} />
                        </div>
                        <div className="flex gap-3 text-xs text-slate-400">
                          <span>{Math.round(historyTotals.protein)}/{Math.round(ht.protein_g)}g P</span>
                          <span>{Math.round(historyTotals.carbs)}/{Math.round(ht.carbs_g)}g C</span>
                          <span>{Math.round(historyTotals.fat)}/{Math.round(ht.fat_g)}g F</span>
                        </div>
                      </>
                    );
                  }
                  if (historyEntries && historyEntries.length > 0) {
                    return (
                      <div className="flex flex-wrap gap-x-4 gap-y-1 text-sm text-slate-300">
                        <span className="font-medium text-white">{Math.round(historyTotals.cal)} cal</span>
                        <span>{Math.round(historyTotals.protein)}g P</span>
                        <span>{Math.round(historyTotals.carbs)}g C</span>
                        <span>{Math.round(historyTotals.fat)}g F</span>
                        {historyTotals.caffeine > 0 && <span>{Math.round(historyTotals.caffeine)}mg caf</span>}
                      </div>
                    );
                  }
                  return <p className="text-sm text-slate-500">No entries for this date.</p>;
                })()}
              </div>

              {/* Add entry to selected date — same input modes as Today, but
                  every flow targets `entryDate` (= selectedDate on this tab).
                  Hidden while a flow is mid-action so the user isn't shown two
                  competing surfaces. */}
              {!showForm && !photoPreview && !barcodeResult && !scannerOpen && (
                <div
                  className="bg-slate-800 rounded-xl border border-slate-700/50 p-4 space-y-3"
                  data-testid="history-add-entry-form"
                >
                  <div className="flex items-center justify-between">
                    <h2 className="text-sm font-semibold text-white">
                      Add to {selectedDate === today ? 'today' : formatDateShort(selectedDate)}
                    </h2>
                    {isBackfill && (
                      <span className="text-[10px] text-amber-400 bg-amber-900/30 border border-amber-700/40 rounded px-1.5 py-0.5">
                        backfill
                      </span>
                    )}
                  </div>

                  <div className="grid grid-cols-3 gap-3">
                    <button
                      onClick={() => photoRef.current?.click()}
                      className="flex flex-col items-center justify-center gap-2 bg-slate-900 rounded-xl border border-slate-700/50 p-3 min-h-[80px] active:bg-slate-700 transition-colors"
                      data-testid="history-add-photo"
                    >
                      <svg className="w-6 h-6 text-blue-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                        <path strokeLinecap="round" strokeLinejoin="round" d="M6.827 6.175A2.31 2.31 0 015.186 7.23c-.38.054-.757.112-1.134.175C2.999 7.58 2.25 8.507 2.25 9.574V18a2.25 2.25 0 002.25 2.25h15A2.25 2.25 0 0021.75 18V9.574c0-1.067-.75-1.994-1.802-2.169a47.865 47.865 0 00-1.134-.175 2.31 2.31 0 01-1.64-1.055l-.822-1.316a2.192 2.192 0 00-1.736-1.039 48.774 48.774 0 00-5.232 0 2.192 2.192 0 00-1.736 1.039l-.821 1.316z" />
                        <path strokeLinecap="round" strokeLinejoin="round" d="M16.5 12.75a4.5 4.5 0 11-9 0 4.5 4.5 0 019 0z" />
                      </svg>
                      <span className="text-[11px] text-slate-400">Photo</span>
                    </button>
                    <button
                      onClick={startScanner}
                      className="flex flex-col items-center justify-center gap-2 bg-slate-900 rounded-xl border border-slate-700/50 p-3 min-h-[80px] active:bg-slate-700 transition-colors"
                      data-testid="history-add-scan"
                    >
                      <svg className="w-6 h-6 text-purple-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                        <path strokeLinecap="round" strokeLinejoin="round" d="M3.75 4.875c0-.621.504-1.125 1.125-1.125h4.5c.621 0 1.125.504 1.125 1.125v4.5c0 .621-.504 1.125-1.125 1.125h-4.5A1.125 1.125 0 013.75 9.375v-4.5zM3.75 14.625c0-.621.504-1.125 1.125-1.125h4.5c.621 0 1.125.504 1.125 1.125v4.5c0 .621-.504 1.125-1.125 1.125h-4.5a1.125 1.125 0 01-1.125-1.125v-4.5zM13.5 4.875c0-.621.504-1.125 1.125-1.125h4.5c.621 0 1.125.504 1.125 1.125v4.5c0 .621-.504 1.125-1.125 1.125h-4.5A1.125 1.125 0 0113.5 9.375v-4.5z" />
                      </svg>
                      <span className="text-[11px] text-slate-400">Scan</span>
                    </button>
                    <button
                      onClick={() => {
                        setFormData((prev) => ({ ...prev, date: entryDate }));
                        setShowForm(true);
                      }}
                      className="flex flex-col items-center justify-center gap-2 bg-slate-900 rounded-xl border border-slate-700/50 p-3 min-h-[80px] active:bg-slate-700 transition-colors"
                      data-testid="history-add-typeit"
                    >
                      <svg className="w-6 h-6 text-emerald-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                        <path strokeLinecap="round" strokeLinejoin="round" d="M16.862 4.487l1.687-1.688a1.875 1.875 0 112.652 2.652L10.582 16.07a4.5 4.5 0 01-1.897 1.13L6 18l.8-2.685a4.5 4.5 0 011.13-1.897l8.932-8.931zm0 0L19.5 7.125M18 14v4.75A2.25 2.25 0 0115.75 21H5.25A2.25 2.25 0 013 18.75V8.25A2.25 2.25 0 015.25 6H10" />
                      </svg>
                      <span className="text-[11px] text-slate-400">Type / look up</span>
                    </button>
                  </div>

                  {/* Quick re-log from the fueling shelf — also respects entryDate. */}
                  {shelfItems && shelfItems.length > 0 && (
                    <div>
                      <p className="text-[11px] text-slate-500 mb-1.5">Quick from your shelf</p>
                      <div className="flex gap-2 overflow-x-auto pb-1 -mx-1 px-1 scrollbar-none">
                        {shelfItems.map((item) => (
                          <button
                            key={item.id}
                            onClick={() => handleShelfTap(item.product.id, `${item.product.brand} ${item.product.product_name}`)}
                            className="flex-shrink-0 flex flex-col items-start bg-slate-700/60 rounded-lg border border-slate-600/50 px-2.5 py-1.5 min-w-[100px] max-w-[130px] min-h-[48px] active:bg-slate-600 transition-colors"
                          >
                            <span className="text-[10px] text-slate-500 leading-tight">{item.product.brand}</span>
                            <span className="text-[11px] font-medium text-white leading-tight line-clamp-2">
                              {item.product.product_name}{item.product.variant ? ` ${item.product.variant}` : ''}
                            </span>
                          </button>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              )}

              {/* Selected Date Entries */}
              {historyEntries && historyEntries.length > 0 && (
                <div className="space-y-2">
                  <h2 className="text-sm font-semibold text-slate-400 px-1">Entries</h2>
                  {historyEntries.map((entry) => (
                    <div key={entry.id} className="bg-slate-800 rounded-xl border border-slate-700/50 p-3">
                      {editingEntryId === entry.id ? (
                        <div className="space-y-3" data-testid={`history-edit-form-${entry.id}`}>
                          <div>
                            <label className="block text-xs text-slate-500 mb-1">Notes</label>
                            <input
                              value={editForm.notes ?? ''}
                              onChange={(e) => setEditForm({ ...editForm, notes: e.target.value })}
                              className="w-full px-3 py-2 bg-slate-900 border border-slate-700/50 rounded-lg text-white text-sm min-h-[44px]"
                            />
                          </div>
                          <div className="grid grid-cols-4 gap-2">
                            <div>
                              <label className="block text-[10px] text-slate-500 mb-0.5">Cal</label>
                              <input
                                type="number"
                                value={editForm.calories ?? ''}
                                onChange={(e) =>
                                  setEditForm({
                                    ...editForm,
                                    calories: e.target.value ? Number(e.target.value) : undefined,
                                  })
                                }
                                className="w-full px-2 py-1.5 bg-slate-900 border border-slate-700/50 rounded text-white text-sm"
                              />
                            </div>
                            <div>
                              <label className="block text-[10px] text-slate-500 mb-0.5">Protein</label>
                              <input
                                type="number"
                                value={editForm.protein_g ?? ''}
                                onChange={(e) =>
                                  setEditForm({
                                    ...editForm,
                                    protein_g: e.target.value ? Number(e.target.value) : undefined,
                                  })
                                }
                                className="w-full px-2 py-1.5 bg-slate-900 border border-slate-700/50 rounded text-white text-sm"
                              />
                            </div>
                            <div>
                              <label className="block text-[10px] text-slate-500 mb-0.5">Carbs</label>
                              <input
                                type="number"
                                value={editForm.carbs_g ?? ''}
                                onChange={(e) =>
                                  setEditForm({
                                    ...editForm,
                                    carbs_g: e.target.value ? Number(e.target.value) : undefined,
                                  })
                                }
                                className="w-full px-2 py-1.5 bg-slate-900 border border-slate-700/50 rounded text-white text-sm"
                              />
                            </div>
                            <div>
                              <label className="block text-[10px] text-slate-500 mb-0.5">Fat</label>
                              <input
                                type="number"
                                value={editForm.fat_g ?? ''}
                                onChange={(e) =>
                                  setEditForm({
                                    ...editForm,
                                    fat_g: e.target.value ? Number(e.target.value) : undefined,
                                  })
                                }
                                className="w-full px-2 py-1.5 bg-slate-900 border border-slate-700/50 rounded text-white text-sm"
                              />
                            </div>
                          </div>
                          <div className="flex gap-2 justify-end">
                            <button
                              onClick={() => handleDeleteEntry(entry.id)}
                              disabled={deleteEntry.isPending}
                              className="px-3 py-1.5 text-red-400 text-xs hover:bg-red-400/10 rounded min-h-[36px]"
                            >
                              Delete
                            </button>
                            <button
                              onClick={() => setEditingEntryId(null)}
                              className="px-3 py-1.5 text-slate-400 text-xs hover:bg-slate-700 rounded min-h-[36px]"
                            >
                              Cancel
                            </button>
                            <button
                              onClick={handleHistorySaveEdit}
                              disabled={updateEntry.isPending}
                              className="px-3 py-1.5 bg-blue-600 hover:bg-blue-500 text-white text-xs rounded min-h-[36px]"
                              data-testid={`history-edit-save-${entry.id}`}
                            >
                              {updateEntry.isPending ? 'Saving...' : 'Save'}
                            </button>
                          </div>
                        </div>
                      ) : (
                        <button
                          onClick={() => startEditing(entry)}
                          className="w-full text-left"
                          data-testid={`history-entry-${entry.id}`}
                        >
                          <div className="flex justify-between items-start">
                            <div className="min-w-0 flex-1">
                              {entry.notes && <p className="text-sm text-white truncate">{entry.notes}</p>}
                              <div className="flex items-center gap-2 text-xs text-slate-400 mt-0.5">
                                <span className="capitalize">{entry.entry_type.replace(/_/g, ' ')}</span>
                                {macroSourceBadge(entry.macro_source)}
                              </div>
                            </div>
                            <div className="flex items-center gap-2 flex-shrink-0 ml-2">
                              <div className="text-right text-xs text-slate-300">
                                {entry.calories != null && <div>{Math.round(entry.calories)} cal</div>}
                                <div className="text-slate-500">
                                  {entry.protein_g != null && `${Math.round(entry.protein_g)}P `}
                                  {entry.carbs_g != null && `${Math.round(entry.carbs_g)}C `}
                                  {entry.fat_g != null && `${Math.round(entry.fat_g)}F`}
                                </div>
                              </div>
                              <svg className="w-3.5 h-3.5 text-slate-600" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                                <path strokeLinecap="round" strokeLinejoin="round" d="M16.862 4.487l1.687-1.688a1.875 1.875 0 112.652 2.652L10.582 16.07a4.5 4.5 0 01-1.897 1.13L6 18l.8-2.685a4.5 4.5 0 011.13-1.897l8.932-8.931z" />
                              </svg>
                            </div>
                          </div>
                        </button>
                      )}
                    </div>
                  ))}
                </div>
              )}

              {/* 7-Day Summary */}
              {summary7 && (
                <div className="bg-slate-800 rounded-xl border border-slate-700/50 p-4 space-y-3">
                  <h2 className="text-sm font-semibold text-slate-300">7-Day Summary</h2>
                  <div className="space-y-1.5">
                    {summary7.days.map((day: DaySummary) => {
                      const maxCal = Math.max(...summary7.days.map((d: DaySummary) => d.calories), 1);
                      const barWidth = day.entry_count > 0 ? Math.max(4, (day.calories / maxCal) * 100) : 0;
                      return (
                        <div key={day.date} className="flex items-center gap-2 text-xs">
                          <span className="text-slate-500 w-12 flex-shrink-0">{formatDateShort(day.date)}</span>
                          <div className="flex-1 h-5 bg-slate-700/50 rounded overflow-hidden">
                            {barWidth > 0 && (
                              <div
                                className="h-full bg-blue-600/60 rounded flex items-center pl-1.5"
                                style={{ width: `${barWidth}%` }}
                              >
                                <span className="text-[10px] text-white font-medium whitespace-nowrap">
                                  {Math.round(day.calories)}
                                </span>
                              </div>
                            )}
                          </div>
                          <span className="text-slate-500 w-24 text-right flex-shrink-0">
                            {day.entry_count > 0
                              ? `${Math.round(day.protein_g)}P ${Math.round(day.carbs_g)}C ${Math.round(day.fat_g)}F`
                              : '—'}
                          </span>
                        </div>
                      );
                    })}
                  </div>
                  <p className="text-xs text-slate-500 pt-1 border-t border-slate-700">
                    Avg: {Math.round(summary7.period_avg_calories)} cal/day — logged {summary7.days_logged}/{summary7.total_days} days
                  </p>
                </div>
              )}

              {/* Export */}
              <button
                onClick={handleExportCsv}
                disabled={exporting}
                className="w-full py-3 bg-slate-800 hover:bg-slate-700 disabled:opacity-50 border border-slate-700/50 rounded-xl text-sm font-medium text-slate-300 min-h-[44px] transition-colors"
              >
                {exporting ? 'Exporting...' : 'Download CSV (last 90 days)'}
              </button>
            </>
          )}

          {/* ======================== TAB 3: INSIGHTS ======================== */}
          {activeTab === 'insights' && (
            <>
              {/* Weekly Averages */}
              {summary7 && (
                <div className="bg-slate-800 rounded-xl border border-slate-700/50 p-4 space-y-4">
                  <h2 className="text-sm font-semibold text-slate-300">Weekly Averages</h2>

                  <div className="text-center">
                    <p className="text-3xl font-bold text-white">{Math.round(summary7.period_avg_calories)}</p>
                    <p className="text-xs text-slate-500 mt-0.5">avg cal/day</p>
                  </div>

                  {/* Macro split bars */}
                  {(() => {
                    const totalG = summary7.period_avg_protein_g + summary7.period_avg_carbs_g + summary7.period_avg_fat_g;
                    if (totalG === 0) return <p className="text-xs text-slate-500 text-center">No macro data yet</p>;
                    const pPct = Math.round((summary7.period_avg_protein_g / totalG) * 100);
                    const cPct = Math.round((summary7.period_avg_carbs_g / totalG) * 100);
                    const fPct = 100 - pPct - cPct;
                    return (
                      <div className="space-y-2">
                        <div className="flex h-3 rounded-full overflow-hidden">
                          <div className="bg-red-500/70" style={{ width: `${pPct}%` }} />
                          <div className="bg-yellow-500/70" style={{ width: `${cPct}%` }} />
                          <div className="bg-blue-500/70" style={{ width: `${fPct}%` }} />
                        </div>
                        <div className="flex justify-between text-xs">
                          <span className="text-red-400">P: {Math.round(summary7.period_avg_protein_g)}g ({pPct}%)</span>
                          <span className="text-yellow-400">C: {Math.round(summary7.period_avg_carbs_g)}g ({cPct}%)</span>
                          <span className="text-blue-400">F: {Math.round(summary7.period_avg_fat_g)}g ({fPct}%)</span>
                        </div>
                      </div>
                    );
                  })()}

                  <p className="text-xs text-slate-500 pt-2 border-t border-slate-700">
                    {summary7.days_logged}/{summary7.total_days} days logged this week
                  </p>
                </div>
              )}

              {/* 30-Day Trends */}
              {summary30 && (
                <div className="bg-slate-800 rounded-xl border border-slate-700/50 p-4 space-y-3">
                  <h2 className="text-sm font-semibold text-slate-300">30-Day Trends</h2>
                  <TrendChart days={summary30.days} />
                  <div className="grid grid-cols-4 gap-2 text-center">
                    <div>
                      <p className="text-sm font-semibold text-white">{Math.round(summary30.period_avg_calories)}</p>
                      <p className="text-[10px] text-slate-500">cal/day</p>
                    </div>
                    <div>
                      <p className="text-sm font-semibold text-red-400">{Math.round(summary30.period_avg_protein_g)}g</p>
                      <p className="text-[10px] text-slate-500">protein</p>
                    </div>
                    <div>
                      <p className="text-sm font-semibold text-yellow-400">{Math.round(summary30.period_avg_carbs_g)}g</p>
                      <p className="text-[10px] text-slate-500">carbs</p>
                    </div>
                    <div>
                      <p className="text-sm font-semibold text-blue-400">{Math.round(summary30.period_avg_fat_g)}g</p>
                      <p className="text-[10px] text-slate-500">fat</p>
                    </div>
                  </div>
                </div>
              )}

              {/* Pre-Run Fueling */}
              <div className="bg-slate-800 rounded-xl border border-slate-700/50 p-4 space-y-3">
                <h2 className="text-sm font-semibold text-slate-300">Pre-Run Fueling</h2>
                {activityLinked && activityLinked.activities.length > 0 ? (
                  <div className="space-y-3">
                    {activityLinked.activities.map((act) => (
                      <div key={act.activity_id} className="bg-slate-700/30 rounded-lg p-3 space-y-2">
                        <div className="flex items-center justify-between">
                          <div className="min-w-0 flex-1">
                            <p className="text-sm font-medium text-white truncate">{act.activity_name}</p>
                            <p className="text-xs text-slate-500">
                              {formatDateShort(act.activity_date)}
                              {act.distance_mi != null && ` · ${act.distance_mi.toFixed(1)} mi`}
                            </p>
                          </div>
                        </div>

                        {act.pre_entries.length > 0 && (
                          <div className="pl-2 border-l-2 border-green-700/50 space-y-0.5">
                            <p className="text-[10px] font-medium text-green-400 uppercase">Pre-run</p>
                            {act.pre_entries.map((e, i) => (
                              <p key={i} className="text-xs text-slate-400">
                                {e.notes || 'Entry'} — {Math.round(e.carbs_g)}g C
                                {e.caffeine_mg > 0 && `, ${Math.round(e.caffeine_mg)}mg caf`}
                              </p>
                            ))}
                            <p className="text-xs text-slate-500">
                              Total: {Math.round(act.pre_total_carbs_g)}g carbs
                              {act.pre_total_caffeine_mg > 0 && `, ${Math.round(act.pre_total_caffeine_mg)}mg caffeine`}
                            </p>
                          </div>
                        )}

                        {act.during_entries.length > 0 && (
                          <div className="pl-2 border-l-2 border-yellow-700/50 space-y-0.5">
                            <p className="text-[10px] font-medium text-yellow-400 uppercase">During</p>
                            {act.during_entries.map((e, i) => (
                              <p key={i} className="text-xs text-slate-400">
                                {e.notes || 'Entry'} — {Math.round(e.carbs_g)}g C
                              </p>
                            ))}
                            <p className="text-xs text-slate-500">
                              Total: {Math.round(act.during_total_carbs_g)}g carbs
                            </p>
                          </div>
                        )}

                        {act.post_entries.length > 0 && (
                          <div className="pl-2 border-l-2 border-blue-700/50 space-y-0.5">
                            <p className="text-[10px] font-medium text-blue-400 uppercase">Post-run</p>
                            {act.post_entries.map((e, i) => (
                              <p key={i} className="text-xs text-slate-400">
                                {e.notes || 'Entry'} — {Math.round(e.calories)}cal, {Math.round(e.protein_g)}g P
                              </p>
                            ))}
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="text-xs text-slate-500">
                    Link meals to activities using Pre-Run/During/Post entry types
                  </p>
                )}
              </div>
            </>
          )}

        </div>
      </div>
    </ProtectedRoute>
  );
}
