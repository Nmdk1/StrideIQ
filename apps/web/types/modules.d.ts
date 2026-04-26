// Ambient declaration for bare CSS imports (e.g. mapbox-gl/dist/mapbox-gl.css)
// inside dynamically-imported client components. Next.js handles the actual
// CSS bundling; TypeScript just needs to know the import is valid.
declare module '*.css';
