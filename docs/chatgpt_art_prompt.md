# SkillQuest art prompt (for ChatGPT image generation)

Copy everything below into ChatGPT.

---

I'm building a pixel-art dungeon-crawler web game called **SkillQuest: The AI Dungeon** (a DSA-learning RPG). Right now all art is hand-coded pixel grids rendered as inline SVG (no image files at all) — 16x16 color-index grids against a small hex palette. I want to replace/supplement these with real generated sprite art to raise the visual quality.

## Style guide

- **Pixel art, NES/SNES-era look.** Crisp, hard pixel edges — no anti-aliasing, no soft gradients, no blur. Flat color fills only.
- **Transparent background** (PNG with alpha channel) on every sprite.
- **Palette to match the app's existing dark cave/dungeon theme:**
  - Void/background black: `#0a0908`
  - Stone (rock): `#201b16`, `#18140f`, `#362f27`
  - Ember/torch orange: `#ff6b3d`
  - Arcane teal (magic/knowledge accent): `#6ee7d0`
  - Gold (mastery/reward accent): `#e8b339`
  - Parchment (bone/pale): `#ece3cf`
  - Blood red (danger/damage): `#c43d3d`
- **Resolution:** native pixel-art canvas of 32x32 or 64x64 px per sprite (I'll scale up in CSS with `image-rendering: pixelated`, so keep it crisp at the small native size, not upscaled/soft).
- **Mood:** damp, torch-lit cave / dungeon. Gritty, a little grimy, not cute or cartoonish.

## Assets needed (please generate each as a separate image)

1. **Bat, 2-frame flying animation** (wings up / wings down) — small, silhouette-style, dark grey/black with a hint of the arcane teal in the eyes. This is ambient cave atmosphere that flies across the screen periodically.
2. **Six hero characters** (3 male, 3 female), each a full-body pixel character, front-facing, holding or implying their signature power:
   - Titan Warrick (male, heavy armored warrior, red/grey palette) — power: a critical smashing blow
   - Zephyr the Sage (male, robed mage, teal/gold palette) — power: arcane XP surge
   - Kael Shadowstep (male, cloaked rogue, dark purple/grey palette) — power: a shadowy verdict-upgrading strike
   - Freya Ironheart (female, valkyrie warrior, gold/white palette) — power: a healing charge attack
   - Lyra Mindweave (female, mystic, teal/purple palette) — power: revealing hidden knowledge (hint)
   - Nyx Quickblade (female, swift rogue, red/parchment palette) — power: restoring focus (hint tokens)
3. **Five dungeon monsters**, one per knowledge "depth tier," from weakest to strongest:
   - Wraith (ghostly, teal glow) — shallow topics (arrays, linked lists, etc.)
   - Bone Sentinel (skeleton, bone-white/red) — mid topics (trees, heaps)
   - Ember Imp (small fire demon, orange/black) — deeper topics (graphs)
   - Stone Golem (rock creature, grey/brown) — advanced topics (DP)
   - The Big-O Devourer (a large dragon, the final boss) — biggest, most detailed, orange/red/black
4. **One seamless tileable cave rock-wall texture** (dark stone, subtle cracks, no obvious repeat seams) — for use as a background texture, roughly 128x128 or 256x256 px, low contrast so text stays readable on top of it.
5. **A small "hit impact" burst/spark effect** (3-4 frame animation), red/orange, for a monster getting struck — something that can flash briefly over a sprite on a landed hit.

## What to hand back

Please generate these as individual PNG files (or a labeled sprite sheet) with transparent backgrounds where noted. When you send them back, I'll hand them to Claude Code to wire into the actual game — no need to write any code yourself, just the images.
