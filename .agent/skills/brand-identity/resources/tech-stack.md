# Preferred Tech Stack & Implementation Rules

When generating code or UI components for **Obsidian Logic AI**, you **MUST** strictly adhere to the following technology choices.

## Core Stack
* **Framework:** React (TypeScript preferred)
* **Styling Engine:** Tailwind CSS
* **Font Loading:** Ensure `Montserrat` and `Madefor Display` are loaded via `next/font` or CSS import.

## Implementation Guidelines

### 1. Tailwind Usage & Colors
* **Primary Buttons:** Use the brand yellow: `bg-[#F9C74F] text-[#0E0E0E] hover:opacity-90`.
* **Dark Sections:** Use the Obsidian Black: `bg-[#0E0E0E] text-[#FCF0D5]`.
* **Border Radius:** Enforce the specific `7px` radius (approx `rounded-md` or custom `rounded-[7px]`).

### 2. Typography Rules
* **Headings:** Apply `font-display` (Madefor Display) for H1/H2.
* **Body Text:** Apply `font-body` (Montserrat) for paragraphs.
* **H1 Sizing:** target `text-[90px]` on desktop, responsive scaling for mobile.

### 3. Layout Patterns
* **Cards:** White background with subtle shadows, `rounded-[7px]`.
* **Forms:** Modern, clean inputs with `#0E0E0E` text.

### 4. Forbidden Patterns
* Do NOT use Serif fonts (Times New Roman, etc).
* Do NOT use rounded-full (pill shapes) for buttons; use the brand standard 7px radius.
