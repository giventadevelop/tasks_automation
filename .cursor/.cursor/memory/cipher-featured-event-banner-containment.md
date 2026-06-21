# Cipher memory: Featured Event banner — fill enclosing container (object-cover)

**Project:** mosc-temp  
**Domain:** frontend  
**Rule:** `.cursor/rules/image_containment_prevention_hero_images_cards.mdc` (Featured Event Card Strip)  
**Date:** 2026-05

## Goal

Featured Events homepage card: left banner image must **fill the entire** `.featured-event-card-media` column (edge-to-edge, no side letterboxing), clipped to card rounded corners, while overall card stays **compact** on mobile.

## Problem

- Image looked **cut off in the middle** / did not span full column height on desktop.
- **Root cause:** `.event-card-banner-media--featured-strip` used fixed `aspect-ratio` (7/2) + `max-height: 9.5rem` on desktop while `.featured-event-card-inner` uses `md:items-stretch`. The details column set row height; the banner box stayed a short fixed box inside the stretched column.

## Solution — containment chain

### 1. Parent clips corners (enclosing container)

```css
.featured-event-card-media {
  overflow: hidden;
  border-top-left-radius: 1rem;
  border-top-right-radius: 1rem;
  line-height: 0;
}
/* md: left column radii only */
```

Inner `.event-card-banner-media--featured-strip` → `border-radius: 0` (parent clips).

### 2. Mobile — compact height (~25% shorter than 5/3 upcoming)

```css
.event-card-banner-media--featured-strip {
  aspect-ratio: 20 / 9;
  width: 100%;
  max-height: 11.25rem;
  border-radius: 0;
  background: #e2e8f0;
}
```

### 3. Desktop — image fills full media column height

```css
@media (min-width: 768px) {
  .featured-event-card-media {
    display: flex;
    flex-direction: column;
    align-self: stretch;
    min-height: 0;
  }
  .featured-event-card-media > a {
    flex: 1 1 auto;
    min-height: 0;
    height: 100%;
  }
  .event-card-banner-media--featured-strip {
    aspect-ratio: auto;
    max-height: none;
    min-height: 100%;
    height: 100%;
    width: 100%;
  }
}
```

### 4. Image fit — object-cover inside enclosing box

```css
.event-card-banner-media--featured-strip .event-card-banner-image,
.event-card-banner-media--featured-strip img {
  object-fit: cover !important;
  object-position: top center !important;
}
```

Overrides global `.event-card-banner-media img { object-fit: contain }` for featured strip only.

### 5. React components

**`EventStripBannerImage.tsx`** — featured variant classes:

```
event-card-banner-media event-card-banner-media--featured-strip h-full w-full
```

**`FeaturedEventsSection.tsx`** — Link wrapper:

```tsx
<Link className="block h-full w-full min-h-0" ...>
  <EventStripBannerImage variant="featured" ... />
</Link>
```

Row: `featured-event-card-inner flex flex-col md:flex-row md:items-stretch`

## Anti-patterns

- Do **not** use desktop `aspect-ratio` + `max-height` on featured strip when row uses `items-stretch`.
- Do **not** use `object-contain` for featured promo strip (causes side gaps on wide columns).
- Do **not** put `border-radius` only on inner media without `overflow: hidden` on `.featured-event-card-media`.

## Files

- `src/app/globals.css`
- `src/components/FeaturedEventsSection.tsx`
- `src/components/EventStripBannerImage.tsx`
- `.cursor/rules/image_containment_prevention_hero_images_cards.mdc`

## When to use contain vs cover

| Context | Fit |
|--------|-----|
| Thumbnails, sponsors, heroes (full art visible) | `object-contain` |
| Featured homepage promo strip (fill column) | `object-cover` in clipped parent |
