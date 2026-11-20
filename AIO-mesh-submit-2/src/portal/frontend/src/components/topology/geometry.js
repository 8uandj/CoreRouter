export function getCurve(a, b, raA = 0, raB = 0) {
  const dx = b.x - a.x;
  const dy = b.y - a.y;
  const isHoriz = Math.abs(dx) >= Math.abs(dy);
  let sx = a.x;
  let sy = a.y;
  let ex = b.x;
  let ey = b.y;

  if (raA > 0 || raB > 0) {
    if (isHoriz) {
      const dir = Math.sign(dx) || 1;
      sx += dir * raA;
      ex -= dir * raB;
    } else {
      const dir = Math.sign(dy) || 1;
      sy += dir * raA;
      ey -= dir * raB;
    }
  }

  return {
    sx,
    sy,
    ex,
    ey,
    cp1x: isHoriz ? (sx + ex) / 2 : sx,
    cp1y: isHoriz ? sy : (sy + ey) / 2,
    cp2x: isHoriz ? (sx + ex) / 2 : ex,
    cp2y: isHoriz ? ey : (sy + ey) / 2,
    isHoriz,
  };
}

export function evalCurve(a, b, t) {
  const c = getCurve(a, b, 0, 0);
  const inverseT = 1 - t;
  const x = (inverseT ** 3) * c.sx
    + 3 * (inverseT ** 2) * t * c.cp1x
    + 3 * inverseT * (t ** 2) * c.cp2x
    + (t ** 3) * c.ex;
  const y = (inverseT ** 3) * c.sy
    + 3 * (inverseT ** 2) * t * c.cp1y
    + 3 * inverseT * (t ** 2) * c.cp2y
    + (t ** 3) * c.ey;
  return { x, y };
}
