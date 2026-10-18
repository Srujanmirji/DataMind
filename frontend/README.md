# Fastshot Landing Page (Frontend)

Self-contained static landing page built with semantic HTML5, modern vanilla CSS, and lightweight vanilla JavaScript.

## Files
- `index.html`: Complete, self-contained landing page (embedded CSS, SVG icons, responsive layout tokens, and entrance animations).
- `assets/`: Image assets and thumbnails.

## How to Preview / Run

### Option 1: Double-click
Simply open `index.html` in any modern web browser (Chrome, Edge, Firefox, Safari).

### Option 2: Local HTTP Server
From this folder or the project root:
```bash
# From the frontend directory:
python -m http.server 3000
```
Then visit: [http://localhost:3000/](http://localhost:3000/) (or [http://localhost:3000/frontend/](http://localhost:3000/frontend/) if serving from repo root).

## Key Features
- **Cinematic Cover Video**: Background video with automated autoplay resilience and low-power handling.
- **Unit-Scaled Desktop Layout**: Fluidly scaled 1560×1008 reference composition (`--u` unit scalers).
- **Responsive Architectures**:
  - **Desktop**: Absolute toolbar coordinates with non-flex right cluster.
  - **Tablet**: One-row fluid toolbar with flex alignment.
  - **Mobile / Compact**: Multi-tier composer layout with CSS checkbox hamburger navigation drawer.
- **Zero Framework Overhead**: Zero external JS dependencies or heavy build chains.
