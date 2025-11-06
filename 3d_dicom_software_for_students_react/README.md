This is a [Next.js](https://nextjs.org) project bootstrapped with [`create-next-app`](https://nextjs.org/docs/app/api-reference/cli/create-next-app).

## Getting Started

First, run the development server:

```bash
npm run dev
# or
yarn dev
# or
pnpm dev
# or
bun dev
```

Open [http://localhost:3000](http://localhost:3000) with your browser to see the result.

You can start editing the page by modifying `app/page.tsx`. The page auto-updates as you edit the file.

This project uses [`next/font`](https://nextjs.org/docs/app/building-your-application/optimizing/fonts) to automatically optimize and load [Geist](https://vercel.com/font), a new font family for Vercel.

## Learn More

To learn more about Next.js, take a look at the following resources:

- [Next.js Documentation](https://nextjs.org/docs) - learn about Next.js features and API.
- [Learn Next.js](https://nextjs.org/learn) - an interactive Next.js tutorial.

You can check out [the Next.js GitHub repository](https://github.com/vercel/next.js) - your feedback and contributions are welcome!

## Deploy on Vercel

The easiest way to deploy your Next.js app is to use the [Vercel Platform](https://vercel.com/new?utm_medium=default-template&filter=next.js&utm_source=create-next-app&utm_campaign=create-next-app-readme) from the creators of Next.js.

Check out our [Next.js deployment documentation](https://nextjs.org/docs/app/building-your-application/deploying) for more details.

## DICOM 3D Annotator - DICOM Viewer & Annotations MVP scaffolding

This project now includes initial scaffolding for a 3D DICOM education tool (upload → annotate → export JSON). Rendering will be added next.

New folders/files:
- `src/types/annotation.ts` — shared types for annotations and export payload
- `src/state/AppState.tsx` — lightweight React context for files, annotations, volume meta
- `src/components/UploadPanel.tsx` — multiple-file DICOM uploader
- `src/components/AnnotationToolbox.tsx` — add marker/arrow/label (placeholders)
- `src/components/AnnotationList.tsx` — list and delete annotations
- `src/components/ExportButton.tsx` — export annotations + metadata to JSON
- `src/lib/dicom/parseDicom.ts` — placeholder quick probe (checks for DICM magic)

Home page (`src/app/page.tsx`) wires these pieces together.

Run locally:
1. Install deps (recommended — will be used once viewer is added):
   ```bash
   npm i three @react-three/fiber @react-three/drei zustand dicom-parser zod
   npm i -D @types/dicom-parser
   ```
2. Start dev server:
   ```bash
   npm run dev
   ```

Notes:
- The DICOM parser is currently a minimal placeholder. Swap to `dicom-parser` or `dcmjs` to read metadata/pixels.
- Viewer is a placeholder panel; R3F scene and slice/volume rendering will be implemented next.
- Annotations are stored with normalized coordinates ([0..1]^3). Export includes minimal volume metadata.

Next steps (Milestones):
- M2: Implement real DICOM parsing (sort series, extract dimensions/spacing)
- M3: Slice stack renderer in R3F (then optional volume raymarching)
- M4: Scene placement for annotations + sidebar editing
- M5: Export polish and basic UX improvements
