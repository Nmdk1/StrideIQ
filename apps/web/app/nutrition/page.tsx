'use client';

import { useState, useRef, useCallback, useEffect } from 'react';
import { ProtectedRoute } from '@/components/auth/ProtectedRoute';
import { useAuth } from '@/lib/hooks/useAuth';
import {
  useNutritionEntries,
  useCreateNutritionEntry,
  useParseNutritionText,
  useNLParsingAvailable,
  useParsePhoto,
  useFuelingProducts,
  useFuelingProfile,
  useAddToProfile,
  useRemoveFromProfile,
  useLogFueling,
  useScanBarcode,
} from '@/lib/hooks/queries/nutrition';
import { LoadingSpinner } from '@/components/ui/LoadingSpinner';
import type { NutritionEntryCreate } from '@/lib/api/services/nutrition';

export default function NutritionPage() {
  const { user } = useAuth();
  const today = new Date().toISOString().split('T')[0];
  const { data: entries, isLoading } = useNutritionEntries({ start_date: today, end_date: today });
  const { data: nlAvailable } = useNLParsingAvailable();
  const { data: shelfItems } = useFuelingProfile();
  const { data: allProducts } = useFuelingProducts();
  const createEntry = useCreateNutritionEntry();
  const parseText = useParseNutritionText();
  const parsePhoto = useParsePhoto();
  const logFueling = useLogFueling();
  const scanBarcode = useScanBarcode();
  const addToProfile = useAddToProfile();
  const removeFromProfile = useRemoveFromProfile();

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
        date: today,
        entry_type: 'daily',
        calories: Math.round(totalCal),
        protein_g: Math.round(totalP),
        carbs_g: Math.round(totalC),
        fat_g: Math.round(totalF),
        fiber_g: Math.round(totalFib),
        notes,
        macro_source: primarySource,
      });
      showToast('Meal logged');
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
      await new Promise((r) => setTimeout(r, 100));
      const scanner = new Html5Qrcode('barcode-live-reader', {
        formatsToSupport: [0, 2, 3, 4, 5, 10],
        verbose: false,
      });
      scannerRef.current = scanner;
      await scanner.start(
        { facingMode: 'environment' },
        {
          fps: 10,
          qrbox: { width: 280, height: 120 },
          aspectRatio: 1.0,
        },
        async (decodedText: string) => {
          try {
            const state = scanner.getState?.();
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
              });
            } else {
              showToast('Product not found — try a photo instead');
            }
          } catch {
            showToast('Lookup failed — try again');
          }
        },
        () => { /* ignore scan errors (frames without barcode) */ },
      );
      setScannerLoading(false);
    } catch {
      showToast('Could not access camera');
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
        date: today,
        entry_type: 'daily',
        calories: Math.round(barcodeResult.calories * s),
        protein_g: Math.round(barcodeResult.protein_g * s),
        carbs_g: Math.round(barcodeResult.carbs_g * s),
        fat_g: Math.round(barcodeResult.fat_g * s),
        notes: barcodeResult.food_name,
        macro_source: 'branded_barcode',
      });
      showToast('Logged');
      setBarcodeResult(null);
    } catch {
      showToast('Failed to save');
    }
  };

  const handleShelfTap = async (productId: number, productName: string) => {
    try {
      await logFueling.mutateAsync({ product_id: productId, entry_type: 'daily' });
      showToast(`Logged: ${productName}`);
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
        date: draft.date || prev.date,
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
      showToast('Logged');
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

          {/* Daily Summary */}
          <div className="bg-slate-800 rounded-xl border border-slate-700/50 p-4">
            <h1 className="text-lg font-semibold mb-2">Today&apos;s Nutrition</h1>
            {entries && entries.length > 0 ? (
              <div className="flex flex-wrap gap-x-4 gap-y-1 text-sm text-slate-300">
                <span className="font-medium text-white">{Math.round(totals.cal)} cal</span>
                <span>{Math.round(totals.protein)}g P</span>
                <span>{Math.round(totals.carbs)}g C</span>
                <span>{Math.round(totals.fat)}g F</span>
                {totals.caffeine > 0 && <span>{Math.round(totals.caffeine)}mg caf</span>}
              </div>
            ) : (
              <p className="text-sm text-slate-500">No entries today. Log when convenient.</p>
            )}
          </div>

          {/* Toast */}
          {toast && (
            <div className="fixed top-4 left-1/2 -translate-x-1/2 z-50 bg-green-800/90 text-green-100 px-4 py-2 rounded-lg text-sm shadow-lg">
              {toast}
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
                  onClick={() => setShowForm(true)}
                  className="flex flex-col items-center justify-center gap-2 bg-slate-800 rounded-xl border border-slate-700/50 p-4 min-h-[88px] active:bg-slate-700 transition-colors"
                >
                  <svg className="w-7 h-7 text-emerald-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M16.862 4.487l1.687-1.688a1.875 1.875 0 112.652 2.652L10.582 16.07a4.5 4.5 0 01-1.897 1.13L6 18l.8-2.685a4.5 4.5 0 011.13-1.897l8.932-8.931zm0 0L19.5 7.125M18 14v4.75A2.25 2.25 0 0115.75 21H5.25A2.25 2.25 0 013 18.75V8.25A2.25 2.25 0 015.25 6H10" />
                  </svg>
                  <span className="text-xs text-slate-400">Type it</span>
                </button>
              </div>

              <input
                ref={photoRef}
                type="file"
                accept="image/*"
                capture="environment"
                className="hidden"
                onChange={handlePhotoCapture}
              />
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
                      className="flex-shrink-0 flex flex-col items-center justify-center bg-slate-700/60 rounded-lg border border-slate-600/50 px-3 py-2 min-w-[72px] min-h-[56px] active:bg-slate-600 transition-colors"
                    >
                      <span className="text-xs font-medium text-white truncate max-w-[64px]">
                        {item.product.brand.slice(0, 4)}
                      </span>
                      <span className="text-[10px] text-slate-400 truncate max-w-[64px]">
                        {item.product.caffeine_mg ? `${item.product.caffeine_mg}mg caf` : `${item.product.carbs_g}g C`}
                      </span>
                    </button>
                  ))}
                </div>
              ) : (
                <p className="text-xs text-slate-500">Tap &quot;+ Add products&quot; to build your fueling shelf for one-tap logging.</p>
              )}
            </div>
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
              <h2 className="text-sm font-semibold">{barcodeResult.food_name}</h2>
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

          {/* Text / Custom Entry Form */}
          {showForm && (
            <div className="bg-slate-800 rounded-xl border border-slate-700/50 p-4 space-y-4">
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
                        date: today,
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

          {/* Today's Log */}
          {entries && entries.length > 0 && (
            <div className="space-y-2">
              <h2 className="text-sm font-semibold text-slate-400 px-1">Today&apos;s Log</h2>
              {entries.map((entry) => (
                <div key={entry.id} className="bg-slate-800 rounded-xl border border-slate-700/50 p-3">
                  <div className="flex justify-between items-start">
                    <div className="min-w-0 flex-1">
                      {entry.notes && <p className="text-sm text-white truncate">{entry.notes}</p>}
                      <div className="text-xs text-slate-400 mt-0.5">
                        <span className="capitalize">{entry.entry_type.replace(/_/g, ' ')}</span>
                        {entry.macro_source && (
                          <span className="ml-2 text-slate-500">{entry.macro_source.replace(/_/g, ' ')}</span>
                        )}
                      </div>
                    </div>
                    <div className="text-right text-xs text-slate-300 flex-shrink-0 ml-2">
                      {entry.calories != null && <div>{Math.round(entry.calories)} cal</div>}
                      <div className="text-slate-500">
                        {entry.protein_g != null && `${Math.round(entry.protein_g)}P `}
                        {entry.carbs_g != null && `${Math.round(entry.carbs_g)}C `}
                        {entry.fat_g != null && `${Math.round(entry.fat_g)}F`}
                      </div>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}

        </div>
      </div>
    </ProtectedRoute>
  );
}
