/**
 * The central tap helper (SPEC.md §11).
 *
 * A tap counts only when the finger moved 8 pixels or less between putting it
 * down and lifting it. Without that, scrolling a long list on a phone fires the
 * button the finger happened to start on.
 *
 * The handler is bound to `click`, not to `pointerup`, for two reasons: a
 * keyboard press on a semantic button fires `click` and no pointer events at
 * all (SPEC.md §23), and `click` is what assistive technology triggers. The
 * pointer events only *withdraw* a click that turned out to be a drag.
 *
 * Nothing is ever saved on `touchstart` — that is what this file exists to
 * prevent.
 */

const MAX_TAP_MOVEMENT_PX = 8;

export function onTap(element, handler) {
  let startX = 0;
  let startY = 0;
  let moved = false;

  const onPointerDown = (event) => {
    startX = event.clientX;
    startY = event.clientY;
    moved = false;
  };

  const onPointerUp = (event) => {
    const distance = Math.hypot(event.clientX - startX, event.clientY - startY);
    moved = distance > MAX_TAP_MOVEMENT_PX;
  };

  const onClick = (event) => {
    if (moved) {
      // The pointer travelled: this was a scroll or a drag, not a tap.
      moved = false;
      return;
    }
    handler(event);
  };

  element.addEventListener('pointerdown', onPointerDown);
  element.addEventListener('pointerup', onPointerUp);
  element.addEventListener('click', onClick);

  return () => {
    element.removeEventListener('pointerdown', onPointerDown);
    element.removeEventListener('pointerup', onPointerUp);
    element.removeEventListener('click', onClick);
  };
}
