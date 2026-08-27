// Hand-authored hero pixel sprites + display/effect metadata.
//
// IMPORTANT: hero `id` keys, and the `effect`/`amount`/`xp` fields, must
// exactly match backend/services/heroes.py's HEROES dict -- the real
// backend is authoritative for what a powerup actually does (see
// routes/game.py's use_powerup). If you rename/add a hero or change a
// powerup's effect, update both files together.
//
// TO ADD OR SWAP HERO ART: each entry's `image` points at the real PNG under
// public/sprites/heroes/ (ChatGPT-generated, background-removed) -- <PixelSprite>
// prefers `image` over `grid`/`palette` when both are present. Drop in a new
// PNG at that path to swap the art with zero code changes. `grid`/`palette`
// stay defined as a fallback (and for anyone editing pixel-by-pixel by hand);
// see PixelSprite.jsx for the grid format.

export const HEROES = {
  titan_warrior: {
    name: 'Titan Warrick',
    gender: 'male',
    powerupName: "Titan's Smash",
    powerupDescription: 'Empowers your next answer to deal full damage, as if answered perfectly.',
    effect: 'force_correct',
    image: '/sprites/heroes/titan_warrior.png',
    palette: { k: '#0c0a14', p: '#c43d3d', m: '#8a8f98', d: '#5a5f68', s: '#e8b389', e: '#ece3cf' },
    grid: [
      '......kpkk......',
      '......kppk......',
      '.....kmmmmk.....',
      '.....kssssk.....',
      '.....kseesk.....',
      '....kmmmmmmk....',
      '...kmmmmmmmmk...',
      '...kdmmmmmmdk...',
      '...kdmmmmmmdk...',
      '....kmmmmmmk....',
      '.....kd..dk.....',
      '.....kd..dk.....',
      '.....kd..dk.....',
      '.....kd..dk.....',
      '....kkd..dkk....',
      '................',
    ],
  },

  sage_mage: {
    name: 'Zephyr the Sage',
    gender: 'male',
    powerupName: 'Arcane Surge',
    powerupDescription: 'Doubles the XP earned from your next answer.',
    effect: 'double_xp_next',
    image: '/sprites/heroes/sage_mage.png',
    palette: { k: '#0c0a14', h: '#1a1523', r: '#3a8c7c', s: '#e8b389', e: '#e8b339' },
    grid: [
      '......khhhh.....',
      '.....khhhhhk....',
      '.....kssssk.....',
      '.....kseesk.....',
      '....khrrrrhk....',
      '...krrrrrrrrk...',
      '...krrrrrrrrk...',
      '...krrrrrrrrk...',
      '...krrrrrrrrk...',
      '....krrrrrrk....',
      '.....krrrrk.....',
      '.....kr..rk.....',
      '.....kr..rk.....',
      '.....kr..rk.....',
      '....kkr..rkk....',
      '................',
    ],
  },

  shadow_rogue: {
    name: 'Kael Shadowstep',
    gender: 'male',
    powerupName: 'Shadow Step',
    powerupDescription: "Boosts your next answer's judged score by 30% (capped at a perfect score) -- can turn an incorrect or partial answer into a real hit.",
    effect: 'score_boost_next',
    boost: 0.3,
    image: '/sprites/heroes/shadow_rogue.png',
    palette: { k: '#0c0a14', h: '#2a2438', c: '#18140f', d: '#443d34', s: '#e8b389', e: '#6ee7d0' },
    grid: [
      '......khhhh.....',
      '.....khhhhhk....',
      '.....khesehk....',
      '.....khhhhhk....',
      '....kchhhhck....',
      '...kccccccccck..',
      '...kccccccccck..',
      '...kdccccccdk...',
      '...kccccccccck..',
      '....kccccccck...',
      '.....kc..ck.....',
      '.....kc..ck.....',
      '.....kc..ck.....',
      '.....kc..ck.....',
      '....kkc..ckk....',
      '................',
    ],
  },

  valkyrie_warrior: {
    name: 'Freya Ironheart',
    gender: 'female',
    powerupName: "Valkyrie's Charge",
    powerupDescription: 'Guarantees your next answer deals full damage and heals you to full HP.',
    effect: 'force_correct_heal',
    image: '/sprites/heroes/valkyrie_warrior.png',
    palette: { k: '#0c0a14', g: '#e8b339', m: '#8a8f98', s: '#e8b389', e: '#ece3cf', y: '#e8b339' },
    grid: [
      '......kggkk.....',
      '.....kyyyyk.....',
      '.....kssssk.....',
      '.....kseesk.....',
      '....kmmmmmmk....',
      '...kgmmmmmmgk...',
      '...kgmmmmmmgk...',
      '...kgmmmmmmgk...',
      '...kgmmmmmmgk...',
      '....kmmmmmmk....',
      '.....kg..gk.....',
      '.....kg..gk.....',
      '.....kg..gk.....',
      '.....kg..gk.....',
      '....kkg..gkk....',
      '.....y....y.....',
    ],
  },

  mindweave_mage: {
    name: 'Lyra Mindweave',
    gender: 'female',
    powerupName: "Mind's Eye",
    powerupDescription: 'Reveals a free hint and grants bonus XP.',
    effect: 'free_hint_bonus_xp',
    xp: 20,
    image: '/sprites/heroes/mindweave_mage.png',
    palette: { k: '#0c0a14', h: '#3d2f52', r: '#8e6fc4', s: '#e8b389', e: '#e8b339' },
    grid: [
      '.....khhhhhh....',
      '....khhhhhhhk...',
      '.....kssssk.....',
      '.....kseesk.....',
      '....khrrrrhk....',
      '...krrrrrrrrk...',
      '...krrrrrrrrk...',
      '...krrrrrrrrk...',
      '...krrrrrrrrk...',
      '....krrrrrrk....',
      '.....krrrrk.....',
      '.....kr..rk.....',
      '.....kr..rk.....',
      '.....kr..rk.....',
      '....kkr..rkk....',
      '....hh....hh....',
    ],
  },

  quickblade_rogue: {
    name: 'Nyx Quickblade',
    gender: 'female',
    powerupName: 'Silver Tongue',
    powerupDescription: 'Instantly restores all of your hint tokens.',
    effect: 'refill_hints',
    image: '/sprites/heroes/quickblade_rogue.png',
    palette: { k: '#0c0a14', h: '#2a2438', c: '#18140f', d: '#443d34', s: '#e8b389', e: '#c43d3d', y: '#ece3cf' },
    grid: [
      '......khhhh.....',
      '.....khhhhhk....',
      '.....khesehk....',
      '.....khhhhhk....',
      '....kchhhhck....',
      '...kccccccccck..',
      '...kccccccccck..',
      '...kdccccccdk...',
      '...kccccccccck..',
      '....kccccccck...',
      '.....kc..ck.....',
      '.....kc..ck.....',
      '.....kc..ck.....',
      '.....kc..ck.....',
      '....kkc..ckk....',
      '.......y........',
    ],
  },
};

export const DEFAULT_HERO_ID = 'titan_warrior';

export function heroOrDefault(heroId) {
  return HEROES[heroId] || HEROES[DEFAULT_HERO_ID];
}

// Combat/boss pages show this line when a "queued" powerup (one that alters
// the *next* answer rather than firing immediately) is armed. Kael's boost
// is a partial score bump, not a guaranteed full hit, so it needs its own
// wording -- reusing the force_correct copy for him would overpromise.
export function queuedPowerupText(heroId) {
  const effect = heroOrDefault(heroId).effect;
  if (effect === 'score_boost_next') return 'Your next answer gets a +30% score boost.';
  return 'Your next answer deals full damage, as if answered perfectly.';
}
