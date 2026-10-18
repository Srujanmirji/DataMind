"use client"

import { GlassFold } from "@/components/ui/glass-fold"

// the adjustable settings 21st shows next to the preview
const settings = {
  color1: "#1e3cc8",
  color2: "#06081e",
  color3: "#96d7ff",
  speed: 0.5,
  scale: 1,
  noise: 0.12,
}

export default function GlassFoldDemo(props: Partial<typeof settings>) {
  const config = { ...settings, ...props }

  return (
    <div className="relative h-screen w-full overflow-hidden bg-black">
      <GlassFold {...config} className="absolute inset-0" />
      <div className="absolute inset-x-0 bottom-0 flex flex-wrap items-end justify-between gap-6 p-10 text-white">
        <div>
          <h1 className="text-4xl font-medium tracking-tight">Glass fold</h1>
          <p className="mt-2 max-w-sm text-sm text-white/60">
            One of twenty WebGL shaders from GradFlow. Three colors, no dependencies.
          </p>
        </div>
        <a
          href="https://gradflow.meerbahadin.dev"
          target="_blank"
          rel="noreferrer"
          className="rounded-full border border-white/20 bg-white/10 px-4 py-2 text-sm font-medium backdrop-blur-md transition-colors hover:bg-white/20"
        >
          gradflow.meerbahadin.dev ↗
        </a>
      </div>
    </div>
  )
}
