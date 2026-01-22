# StrideIQ UI Style Guide

Reference: Compare page (`/compare`) and Tools page (`/tools`)

## Page Layout

```tsx
<div className="min-h-screen bg-slate-900 text-slate-100">
  {/* Optional: Gradient overlay */}
  <div className="absolute inset-0 bg-gradient-to-b from-slate-900/50 via-transparent to-black/50 pointer-events-none" />
  
  <div className="relative max-w-5xl mx-auto px-4 py-8">
    {/* Page content */}
  </div>
</div>
```

## Page Header Pattern

```tsx
<div className="mb-6">
  <h1 className="text-3xl font-bold mb-2 flex items-center gap-3">
    <div className="p-2 rounded-xl bg-orange-500/10 ring-1 ring-orange-500/30">
      <IconName className="w-6 h-6 text-orange-400" />
    </div>
    Page Title
  </h1>
  <p className="text-slate-400">
    Page description
  </p>
</div>
```

## Card Styles

### Main Card
```tsx
<Card className="bg-slate-900/80 border-slate-700/50">
  <CardContent className="pt-5 pb-5">
    {/* Content */}
  </CardContent>
</Card>
```

### Secondary/Nested Card
```tsx
<Card className="bg-slate-800/50 border-slate-700/50">
  <CardContent className="pt-4 pb-4">
    {/* Content */}
  </CardContent>
</Card>
```

## Color Palette

| Element | Class |
|---------|-------|
| Page background | `bg-slate-900` |
| Card background | `bg-slate-900/80` |
| Nested card | `bg-slate-800/50` |
| Border | `border-slate-700/50` |
| Text primary | `text-white` |
| Text secondary | `text-slate-400` |
| Text muted | `text-slate-500` |
| Primary accent | `orange-500` / `orange-600` |
| Success | `emerald-500` |
| Warning | `amber-500` |
| Error | `red-500` |

## Buttons

### Primary Button
```tsx
<Button className="bg-orange-600 hover:bg-orange-500 shadow-lg shadow-orange-500/20">
  Action
</Button>
```

### Secondary Button
```tsx
<Button variant="secondary" className="bg-slate-700 hover:bg-slate-600">
  Action
</Button>
```

### Ghost Button
```tsx
<Button variant="ghost" className="text-slate-400 hover:text-white">
  Action
</Button>
```

## Input Fields

```tsx
<input
  className="px-3 py-2 bg-slate-800 border border-slate-600 rounded-lg text-sm focus:border-orange-500 focus:outline-none focus:ring-1 focus:ring-orange-500/50"
/>
```

## Badges

```tsx
<Badge className="bg-orange-500/20 text-orange-400 border-orange-500/30">
  Status
</Badge>
```

## Icon Containers

```tsx
{/* Accent icon */}
<div className="p-2 rounded-xl bg-orange-500/10 ring-1 ring-orange-500/30">
  <Icon className="w-6 h-6 text-orange-400" />
</div>

{/* Muted icon */}
<div className="p-2 rounded-lg bg-slate-700 ring-1 ring-slate-600">
  <Icon className="w-5 h-5 text-slate-400" />
</div>
```

## Loading States

```tsx
<div className="min-h-screen bg-slate-900 flex items-center justify-center">
  <LoadingSpinner size="lg" />
</div>
```

## Empty States

```tsx
<Card className="border-slate-700/50 bg-slate-900/50">
  <CardContent className="py-12 text-center">
    <Icon className="w-12 h-12 text-slate-600 mx-auto mb-4" />
    <h3 className="text-xl font-semibold mb-2">Empty State Title</h3>
    <p className="text-slate-400 mb-4">
      Description text
    </p>
    <Button className="bg-orange-600 hover:bg-orange-500">
      Action
    </Button>
  </CardContent>
</Card>
```
