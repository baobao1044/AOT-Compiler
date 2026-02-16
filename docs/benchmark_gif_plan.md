# Benchmark GIF plan

## Capture
- Record terminal run:
  - `aotc bench --loop-count 10000000 --repeats 3 --threads 8 --opt O3`
- Use 120-column terminal width for stable layout.

## Render
- Convert recording to GIF (asciinema + agg suggested).
- Trim to 8-12 seconds and include title card: `AOTC v0.1 benchmark`.

## Publish targets
- README snippet
- Blog post section
- Twitter/X and Reddit post assets
