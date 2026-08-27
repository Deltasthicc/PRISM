// Ambient cave bat -- two hand-drawn wing frames swapped on an interval by
// <BatSwarm> for a simple flapping animation. Edit these grids (or add more
// frames and update BatSwarm's frame list) to change how the bat looks.

export const BAT_PALETTE = { k: '#15101f', e: '#c43d3d' };

// Each frame carries both the real PNG (public/sprites/bats/, ChatGPT-
// generated + background-removed) and the original hand-drawn grid as a
// fallback -- <PixelSprite> prefers `image` when present.
export const BAT_FRAMES = [
  {
    // wings up
    image: '/sprites/bats/bat_wings_up.png',
    grid: [
      '....k.....k....',
      '...kk.....kk...',
      '..kk.......kk..',
      '.kk.........kk.',
      'k.....kk.....k.',
      '......ee.......',
      '................',
    ],
  },
  {
    // wings down
    image: '/sprites/bats/bat_wings_down.png',
    grid: [
      '................',
      '....k.....k....',
      '...kk..kk..kk...',
      '..kk...kk...kk..',
      'k....kkkkkk....k',
      '......ee.......',
      '................',
    ],
  },
];
